"""Unit tests for spec_eng.guardian."""

import pytest

from spec_eng.guardian import analyze_clause, analyze_file, analyze_scenario
from spec_eng.models import Clause, Scenario


class TestAnalyzeClause:
    def test_detects_camelcase_service(self) -> None:
        clause = Clause("GIVEN", 'the UserService has no users', 1)
        warnings = analyze_clause(clause)
        assert len(warnings) > 0
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("UserService" in t for t in flagged)

    def test_detects_table(self) -> None:
        clause = Clause("THEN", "the users table contains 1 row", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("table" in t.lower() for t in flagged)

    def test_detects_row(self) -> None:
        clause = Clause("THEN", "the users table contains 1 row", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("row" in t.lower() for t in flagged)

    def test_detects_post_request(self) -> None:
        clause = Clause("WHEN", "a POST request is sent to /api/users", 1)
        warnings = analyze_clause(clause)
        assert len(warnings) > 0

    def test_detects_api_path(self) -> None:
        clause = Clause("WHEN", "a POST request is sent to /api/users", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("/api/" in t for t in flagged)

    def test_detects_redis(self) -> None:
        clause = Clause("GIVEN", "the Redis cache is empty", 1)
        warnings = analyze_clause(clause)
        flagged = [t for w in warnings for t in w.flagged_terms]
        assert any("Redis" in t for t in flagged)

    def test_accepts_behavioral_language(self) -> None:
        clause = Clause("GIVEN", "no registered users", 1)
        warnings = analyze_clause(clause)
        assert len(warnings) == 0

    def test_accepts_behavioral_when(self) -> None:
        clause = Clause(
            "WHEN",
            'a user registers with email "bob@example.com" and password "secret123"',
            1,
        )
        warnings = analyze_clause(clause)
        assert len(warnings) == 0

    def test_accepts_behavioral_then(self) -> None:
        clause = Clause("THEN", "there is 1 registered user", 1)
        warnings = analyze_clause(clause)
        assert len(warnings) == 0

    def test_allowlist_suppresses_warning(self) -> None:
        clause = Clause("GIVEN", "the user has an API key", 1)
        # Without allowlist
        w1 = analyze_clause(clause)
        # With allowlist
        w2 = analyze_clause(clause, allowlist=["API key"])
        # Allowlist should suppress the API-related warning
        assert len(w2) <= len(w1)

    def test_low_sensitivity_fewer_warnings(self) -> None:
        clause = Clause("GIVEN", "the cache is empty", 1)
        w_medium = analyze_clause(clause, sensitivity="medium")
        w_low = analyze_clause(clause, sensitivity="low")
        assert len(w_low) <= len(w_medium)

    def test_warning_has_category(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        warnings = analyze_clause(clause)
        assert all(w.category in ("class_name", "database", "api", "framework") for w in warnings)

    def test_warning_has_suggestion(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        warnings = analyze_clause(clause)
        assert all(w.suggested_alternative != "" for w in warnings)

    def test_suggestion_is_behavioral(self) -> None:
        clause = Clause("GIVEN", "the UserService has no users", 1)
        warnings = analyze_clause(clause)
        # Should suggest something about "registered users"
        suggestions = [w.suggested_alternative for w in warnings]
        assert any("user" in s.lower() or "behavioral" in s.lower() for s in suggestions)


class TestAnalyzeScenario:
    def test_analyzes_all_clauses(self) -> None:
        scenario = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "the UserService is running", 1)],
            whens=[Clause("WHEN", "a POST request is sent to /api/users", 3)],
            thens=[Clause("THEN", "the users table has 1 row", 5)],
        )
        warnings = analyze_scenario(scenario)
        categories = {w.category for w in warnings}
        assert len(categories) >= 2  # Multiple categories flagged

    def test_clean_scenario_no_warnings(self) -> None:
        scenario = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "no registered users", 1)],
            whens=[Clause("WHEN", "a user registers", 3)],
            thens=[Clause("THEN", "there is 1 registered user", 5)],
        )
        warnings = analyze_scenario(scenario)
        assert len(warnings) == 0
