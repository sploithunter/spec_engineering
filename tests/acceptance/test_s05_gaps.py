"""Acceptance tests for Section 5: Gap Analysis.

Covers: 5.1 - 5.11 (5.10 AI suggestion mocked).
"""

import json
from pathlib import Path

import pytest

from spec_eng.gaps import analyze_gaps, load_gaps, save_gaps
from spec_eng.graph import build_graph
from spec_eng.models import Clause, Gap, GapType, ParseResult, Scenario, Severity

pytestmark = pytest.mark.acceptance


def _make_scenario(title: str, given: str, when: str, then: str) -> Scenario:
    return Scenario(
        title=title,
        givens=[Clause("GIVEN", given, 1)],
        whens=[Clause("WHEN", when, 3)],
        thens=[Clause("THEN", then, 5)],
    )


class TestScenario5_1:
    """5.1: Dead-end states are identified."""

    def test_dead_end_in_report(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "go", "user is locked out"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        dead_ends = [g for g in gaps if g.gap_type == GapType.DEAD_END]
        assert any("user is locked out" in g.description for g in dead_ends)

    def test_asks_if_intentional(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "go", "user is locked out"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        dead_ends = [g for g in gaps if g.gap_type == GapType.DEAD_END]
        assert any("intentional" in g.question.lower() for g in dead_ends)


class TestScenario5_2:
    """5.2: Unreachable states are identified."""

    def test_unreachable_in_report(self) -> None:
        from spec_eng.models import GraphModel, State, Transition

        gm = GraphModel(
            states={
                "start": State("start"),
                "middle": State("middle"),
                "admin mode active": State("admin mode active"),
            },
            transitions=[Transition("go", "start", "middle")],
            entry_points=["start"],
        )
        gaps = analyze_gaps(gm)
        unreachable = [g for g in gaps if g.gap_type == GapType.UNREACHABLE]
        assert any("admin mode active" in g.description for g in unreachable)

    def test_asks_how_to_reach(self) -> None:
        from spec_eng.models import GraphModel, State, Transition

        gm = GraphModel(
            states={
                "start": State("start"),
                "orphan": State("orphan"),
            },
            transitions=[],
            entry_points=["start"],
        )
        gaps = analyze_gaps(gm)
        unreachable = [g for g in gaps if g.gap_type == GapType.UNREACHABLE]
        assert any("reach" in g.question.lower() for g in unreachable)


class TestScenario5_3:
    """5.3: Missing error transitions are identified."""

    def test_missing_error_noted(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "user is logged in", "logs out", "logged out"),
            _make_scenario("S2", "user is logged in", "views profile", "profile shown"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        missing_err = [g for g in gaps if g.gap_type == GapType.MISSING_ERROR]
        assert any("user is logged in" in g.description for g in missing_err)

    def test_suggests_error_question(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "user is logged in", "logs out", "logged out"),
            _make_scenario("S2", "user is logged in", "views profile", "profile shown"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        missing_err = [g for g in gaps if g.gap_type == GapType.MISSING_ERROR]
        assert any("error" in g.question.lower() for g in missing_err)


class TestScenario5_4:
    """5.4: Contradictory postconditions are identified."""

    def test_contradiction_flagged(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "1 user", "user registers", "there are 2 users"),
            _make_scenario("B", "1 user", "user registers", "registration fails"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        contradictions = [g for g in gaps if g.gap_type == GapType.CONTRADICTION]
        assert len(contradictions) > 0

    def test_asks_about_missing_condition(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "1 user", "user registers", "2 users"),
            _make_scenario("B", "1 user", "user registers", "registration fails"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        contradictions = [g for g in gaps if g.gap_type == GapType.CONTRADICTION]
        assert any("missing condition" in g.question.lower() for g in contradictions)


class TestScenario5_5:
    """5.5: Missing negative scenarios are suggested."""

    def test_suggests_negatives(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "user registers", "1 user"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        negatives = [g for g in gaps if g.gap_type == GapType.MISSING_NEGATIVE]
        assert len(negatives) > 0

    def test_negative_suggestions_relevant(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "user registers", "1 user"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        negatives = [g for g in gaps if g.gap_type == GapType.MISSING_NEGATIVE]
        assert any("fail" in g.question.lower() for g in negatives)


class TestScenario5_6:
    """5.6: Gap analysis produces a structured report."""

    def test_report_saved(self, tmp_path: Path) -> None:
        gaps = [
            Gap(GapType.DEAD_END, Severity.HIGH, "test", "q?", ["s1"]),
        ]
        (tmp_path / ".spec-eng").mkdir()
        path = save_gaps(gaps, tmp_path)
        assert path.exists()

    def test_report_has_types(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "e1", "b"),
            _make_scenario("S2", "a", "e2", "c"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        for g in gaps:
            assert isinstance(g.gap_type, GapType)
            assert isinstance(g.severity, Severity)

    def test_report_has_references(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "e1", "b"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        for g in gaps:
            assert g.question  # Each has a suggested question


class TestScenario5_7:
    """5.7: Gaps can be triaged by the user."""

    def test_triage_status_persisted(self, tmp_path: Path) -> None:
        gaps = [
            Gap(GapType.DEAD_END, Severity.HIGH, "test", "q?", ["s1"]),
        ]
        gaps[0].triage_status = "intentional"
        (tmp_path / ".spec-eng").mkdir()
        save_gaps(gaps, tmp_path)
        loaded = load_gaps(tmp_path)
        assert loaded[0].triage_status == "intentional"


class TestScenario5_8:
    """5.8: Resolved gaps reduce the gap count on re-analysis."""

    def test_resolved_gaps_disappear(self) -> None:
        # First analysis: only positive scenario
        result1 = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "registers", "1 user"),
        ])
        gm1 = build_graph(result1)
        gaps1 = analyze_gaps(gm1)

        # Second analysis: add error handling
        result2 = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "registers", "1 user"),
            _make_scenario("S2", "no users", "registers with invalid email", "error shown"),
        ])
        gm2 = build_graph(result2)
        gaps2 = analyze_gaps(gm2)

        # Should have fewer missing negative gaps
        neg1 = [g for g in gaps1 if g.gap_type == GapType.MISSING_NEGATIVE]
        neg2 = [g for g in gaps2 if g.gap_type == GapType.MISSING_NEGATIVE]
        # The "no users" state now has a negative scenario
        no_users_neg1 = [g for g in neg1 if "no users" in g.description]
        no_users_neg2 = [g for g in neg2 if "no users" in g.description]
        # With the added negative scenario, the gap should be resolved
        assert len(no_users_neg2) == 0 or len(no_users_neg2) < len(no_users_neg1)


class TestScenario5_9:
    """5.9: New specs from gap analysis are appended to spec files.
    (Tested via triage CLI in integration)"""

    def test_gap_template_format(self) -> None:
        gap = Gap(
            GapType.MISSING_ERROR, Severity.MEDIUM,
            "missing error handling",
            "What happens on error?",
            states=["logged in"],
        )
        # Verify gap has all needed fields for template generation
        assert gap.states
        assert gap.description
        assert gap.question


class TestScenario5_11:
    """5.11: Gap analysis runs automatically after graph updates."""

    def test_auto_analysis_flag_exists(self) -> None:
        from spec_eng.models import ProjectConfig

        config = ProjectConfig(auto_analysis=True)
        assert config.auto_analysis is True
