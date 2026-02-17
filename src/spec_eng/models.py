"""Core data models for spec-eng."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class Clause:
    """A single GIVEN, WHEN, or THEN clause."""

    clause_type: str  # "GIVEN", "WHEN", "THEN"
    text: str
    line_number: int

    def __post_init__(self) -> None:
        if self.clause_type not in ("GIVEN", "WHEN", "THEN"):
            raise ValueError(f"Invalid clause type: {self.clause_type}")


@dataclass
class Scenario:
    """A complete GWT scenario with title and clauses."""

    title: str
    givens: list[Clause] = field(default_factory=list)
    whens: list[Clause] = field(default_factory=list)
    thens: list[Clause] = field(default_factory=list)
    source_file: str | None = None
    line_number: int = 0

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty if valid)."""
        errors: list[str] = []
        if not self.title:
            errors.append("Scenario must have a title")
        if not self.givens:
            errors.append("Scenario must have at least one GIVEN clause")
        if not self.whens:
            errors.append("Scenario must have at least one WHEN clause")
        if not self.thens:
            errors.append("Scenario must have at least one THEN clause")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0


@dataclass
class ParseError:
    """An error encountered during parsing."""

    message: str
    line_number: int
    source_file: str | None = None


@dataclass
class ParseResult:
    """Result of parsing one or more GWT files."""

    scenarios: list[Scenario] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0


@dataclass(frozen=True)
class State:
    """A state in the behavioral state machine."""

    label: str
    source_scenarios: tuple[str, ...] = ()


@dataclass
class Transition:
    """A transition (edge) in the state machine."""

    event: str
    from_state: str
    to_state: str
    source_scenario: str | None = None


class GapType(Enum):
    """Types of gaps found in state machine analysis."""

    DEAD_END = "dead-end"
    UNREACHABLE = "unreachable"
    MISSING_ERROR = "missing-error"
    CONTRADICTION = "contradiction"
    MISSING_NEGATIVE = "missing-negative"


class Severity(Enum):
    """Severity levels for gaps."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Gap:
    """A gap identified in the state machine."""

    gap_type: GapType
    severity: Severity
    description: str
    question: str
    states: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)
    triage_status: str | None = None  # "needs-spec", "intentional", "out-of-scope"


@dataclass
class GraphModel:
    """The complete state machine graph."""

    states: dict[str, State] = field(default_factory=dict)
    transitions: list[Transition] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    terminal_states: list[str] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)


@dataclass
class GuardianWarning:
    """A warning from the spec guardian about implementation detail leakage."""

    original_text: str
    flagged_terms: list[str]
    suggested_alternative: str
    category: str  # "class_name", "database", "api", "framework"


@dataclass
class ProjectConfig:
    """Project configuration for spec-eng."""

    version: str = "0.1.0"
    language: str = ""
    framework: str = ""
    guardian: dict[str, object] = field(default_factory=lambda: {
        "enabled": True,
        "sensitivity": "medium",
        "allowlist": [],
    })
    vocabulary: list[str] = field(default_factory=list)
    auto_analysis: bool = False
    targets: dict[str, str] = field(default_factory=dict)
