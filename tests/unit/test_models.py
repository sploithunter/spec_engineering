"""Unit tests for spec_eng.models."""

import pytest

from spec_eng.models import (
    Clause,
    Gap,
    GapType,
    GraphModel,
    GuardianWarning,
    ParseError,
    ParseResult,
    ProjectConfig,
    Scenario,
    Severity,
    State,
    Transition,
)


class TestClause:
    def test_create_given(self) -> None:
        c = Clause(clause_type="GIVEN", text="no registered users", line_number=1)
        assert c.clause_type == "GIVEN"
        assert c.text == "no registered users"
        assert c.line_number == 1

    def test_create_when(self) -> None:
        c = Clause(clause_type="WHEN", text="a user registers", line_number=3)
        assert c.clause_type == "WHEN"

    def test_create_then(self) -> None:
        c = Clause(clause_type="THEN", text="there is 1 registered user", line_number=5)
        assert c.clause_type == "THEN"

    def test_invalid_clause_type(self) -> None:
        with pytest.raises(ValueError, match="Invalid clause type"):
            Clause(clause_type="IF", text="something", line_number=1)

    def test_clause_is_frozen(self) -> None:
        c = Clause(clause_type="GIVEN", text="test", line_number=1)
        with pytest.raises(AttributeError):
            c.text = "changed"  # type: ignore[misc]

    def test_clause_equality(self) -> None:
        c1 = Clause(clause_type="GIVEN", text="test", line_number=1)
        c2 = Clause(clause_type="GIVEN", text="test", line_number=1)
        assert c1 == c2


class TestScenario:
    def test_valid_scenario(self) -> None:
        s = Scenario(
            title="User registers",
            givens=[Clause("GIVEN", "no users", 1)],
            whens=[Clause("WHEN", "user registers", 3)],
            thens=[Clause("THEN", "1 user exists", 5)],
        )
        assert s.is_valid
        assert s.validate() == []

    def test_missing_given(self) -> None:
        s = Scenario(
            title="Test",
            whens=[Clause("WHEN", "something", 1)],
            thens=[Clause("THEN", "result", 2)],
        )
        errors = s.validate()
        assert any("GIVEN" in e for e in errors)
        assert not s.is_valid

    def test_missing_when(self) -> None:
        s = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "precondition", 1)],
            thens=[Clause("THEN", "result", 2)],
        )
        errors = s.validate()
        assert any("WHEN" in e for e in errors)

    def test_missing_then(self) -> None:
        s = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "precondition", 1)],
            whens=[Clause("WHEN", "action", 2)],
        )
        errors = s.validate()
        assert any("THEN" in e for e in errors)

    def test_empty_title(self) -> None:
        s = Scenario(
            title="",
            givens=[Clause("GIVEN", "x", 1)],
            whens=[Clause("WHEN", "y", 2)],
            thens=[Clause("THEN", "z", 3)],
        )
        errors = s.validate()
        assert any("title" in e for e in errors)


class TestParseResult:
    def test_success(self) -> None:
        result = ParseResult(scenarios=[Scenario(title="test")])
        assert result.is_success

    def test_failure(self) -> None:
        result = ParseResult(errors=[ParseError("bad", 1)])
        assert not result.is_success


class TestEnums:
    def test_gap_types(self) -> None:
        assert GapType.DEAD_END.value == "dead-end"
        assert GapType.UNREACHABLE.value == "unreachable"
        assert GapType.MISSING_ERROR.value == "missing-error"
        assert GapType.CONTRADICTION.value == "contradiction"
        assert GapType.MISSING_NEGATIVE.value == "missing-negative"

    def test_severity(self) -> None:
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"


class TestState:
    def test_frozen(self) -> None:
        s = State(label="logged in", source_scenarios=("s1",))
        with pytest.raises(AttributeError):
            s.label = "changed"  # type: ignore[misc]

    def test_equality(self) -> None:
        s1 = State(label="logged in", source_scenarios=("s1",))
        s2 = State(label="logged in", source_scenarios=("s1",))
        assert s1 == s2


class TestGraphModel:
    def test_empty_graph(self) -> None:
        g = GraphModel()
        assert g.states == {}
        assert g.transitions == []
        assert g.entry_points == []
        assert g.terminal_states == []


class TestGap:
    def test_create_gap(self) -> None:
        g = Gap(
            gap_type=GapType.DEAD_END,
            severity=Severity.HIGH,
            description="State has no outbound transitions",
            question="Is this intentional?",
            states=["locked out"],
        )
        assert g.gap_type == GapType.DEAD_END
        assert g.triage_status is None


class TestProjectConfig:
    def test_defaults(self) -> None:
        c = ProjectConfig()
        assert c.version == "0.1.0"
        assert c.language == ""
        assert c.guardian["enabled"] is True
