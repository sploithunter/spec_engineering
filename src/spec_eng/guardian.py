"""Spec Guardian: detects implementation detail leakage in GWT specs."""

from __future__ import annotations

import re

from spec_eng.models import Clause, GuardianWarning, Scenario

# Pattern categories with (regex, suggested replacement template)
PATTERNS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "class_name": [
        # CamelCase identifiers (2+ uppercase transitions, min 2 parts)
        (re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b"), "a behavioral description"),
        # *Service, *Repository, *Controller, *Manager, *Factory, *Handler
        (
            re.compile(
                r"\b\w*(?:Service|Repository|Controller|Manager|Factory|Handler)\b"
            ),
            "a behavioral description",
        ),
    ],
    "database": [
        (re.compile(r"\b(?:table|tables)\b", re.IGNORECASE), "collection/group"),
        (re.compile(r"\b(?:row|rows)\b", re.IGNORECASE), "record/entry"),
        (re.compile(r"\b(?:column|columns)\b", re.IGNORECASE), "field/attribute"),
        (re.compile(r"\bschema\b", re.IGNORECASE), "structure"),
        (re.compile(r"\bmigration\b", re.IGNORECASE), "update"),
        (re.compile(r"\bSQL\b"), "query"),
        (re.compile(r"\bdatabase\b", re.IGNORECASE), "data store"),
    ],
    "api": [
        (re.compile(r"\b(?:POST|GET|PUT|DELETE|PATCH)\s+(?:request|to)\b"), "action"),
        (re.compile(r"/api/\S+"), "the system"),
        (re.compile(r"\bendpoint\b", re.IGNORECASE), "capability"),
        (re.compile(r"\bHTTP\b"), "request"),
        (re.compile(r"\bstatus\s+code\b", re.IGNORECASE), "response"),
    ],
    "framework": [
        (re.compile(r"\bRedis\b"), "cache"),
        (re.compile(r"\bKafka\b"), "message queue"),
        (re.compile(r"\bMongoDB\b"), "data store"),
        (re.compile(r"\bcache\b", re.IGNORECASE), "stored data"),
        (re.compile(r"\bqueue\b", re.IGNORECASE), "pending items"),
        (re.compile(r"\bmiddleware\b", re.IGNORECASE), "processing step"),
    ],
}

# Suggestions for common implementation detail patterns
SUGGESTIONS: dict[str, str] = {
    "UserService": "GIVEN no registered users",
    "users table": "registered users",
    "row": "registered user",
    "POST request": "a user registers",
    "/api/users": "a user registers",
    "Redis cache": "no cached sessions",
    "Redis": "cached",
}


def analyze_clause(
    clause: Clause,
    sensitivity: str = "medium",
    allowlist: list[str] | None = None,
) -> list[GuardianWarning]:
    """Analyze a single clause for implementation detail leakage."""
    allowlist = allowlist or []
    warnings: list[GuardianWarning] = []

    text = clause.text

    # Determine which categories to check based on sensitivity
    if sensitivity == "low":
        # Only high-confidence patterns: explicit class names and API routes
        categories = ["class_name", "api"]
    elif sensitivity == "high":
        categories = list(PATTERNS.keys())
    else:  # medium (default)
        categories = list(PATTERNS.keys())

    for category in categories:
        for pattern, default_suggestion in PATTERNS[category]:
            matches = pattern.findall(text)
            for match in matches:
                # Check allowlist
                if any(allowed.lower() in match.lower() for allowed in allowlist):
                    continue

                # For low sensitivity, skip single-word CamelCase
                if sensitivity == "low" and category == "class_name":
                    if not any(
                        kw in match
                        for kw in (
                            "Service", "Repository", "Controller",
                            "Manager", "Factory", "Handler",
                        )
                    ):
                        continue

                # Generate suggestion
                suggestion = _suggest_alternative(
                    text, match, clause.clause_type, default_suggestion
                )

                warnings.append(GuardianWarning(
                    original_text=text,
                    flagged_terms=[match],
                    suggested_alternative=suggestion,
                    category=category,
                ))

    return warnings


def analyze_scenario(
    scenario: Scenario,
    sensitivity: str = "medium",
    allowlist: list[str] | None = None,
) -> list[GuardianWarning]:
    """Analyze all clauses in a scenario."""
    warnings: list[GuardianWarning] = []
    for clause in scenario.givens + scenario.whens + scenario.thens:
        warnings.extend(analyze_clause(clause, sensitivity, allowlist))
    return warnings


def analyze_file(
    scenarios: list[Scenario],
    sensitivity: str = "medium",
    allowlist: list[str] | None = None,
) -> list[GuardianWarning]:
    """Analyze all scenarios from a parsed file."""
    warnings: list[GuardianWarning] = []
    for scenario in scenarios:
        warnings.extend(analyze_scenario(scenario, sensitivity, allowlist))
    return warnings


def _suggest_alternative(
    original: str, flagged: str, clause_type: str, default: str
) -> str:
    """Generate a behavioral alternative suggestion."""
    # Check for known substitutions first
    for impl_term, behavioral in SUGGESTIONS.items():
        if impl_term.lower() in flagged.lower() or impl_term.lower() in original.lower():
            return behavioral

    return default
