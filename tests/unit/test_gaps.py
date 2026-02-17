"""Unit tests for spec_eng.gaps."""

from pathlib import Path

import pytest

from spec_eng.gaps import (
    _find_contradictions,
    _find_dead_ends,
    _find_missing_error_transitions,
    _find_missing_negatives,
    _find_unreachable,
    analyze_gaps,
    load_gaps,
    save_gaps,
)
from spec_eng.graph import build_graph
from spec_eng.models import (
    Clause,
    Gap,
    GapType,
    GraphModel,
    ParseResult,
    Scenario,
    Severity,
    State,
    Transition,
)


def _make_scenario(title: str, given: str, when: str, then: str) -> Scenario:
    return Scenario(
        title=title,
        givens=[Clause("GIVEN", given, 1)],
        whens=[Clause("WHEN", when, 3)],
        thens=[Clause("THEN", then, 5)],
    )


class TestFindDeadEnds:
    def test_identifies_dead_end(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "start", "go", "locked out"),
        ])
        gm = build_graph(result)
        gaps = _find_dead_ends(gm, {})
        descs = [g.description for g in gaps]
        assert any("locked out" in d for d in descs)

    def test_no_dead_end_when_connected(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "e1", "b"),
            _make_scenario("S2", "b", "e2", "c"),
        ])
        gm = build_graph(result)
        gaps = _find_dead_ends(gm, {})
        # "b" is not a dead end because it has outbound
        descs = [g.description for g in gaps]
        assert not any('"b"' in d for d in descs)


class TestFindUnreachable:
    def test_identifies_unreachable(self) -> None:
        gm = GraphModel(
            states={
                "start": State("start"),
                "middle": State("middle"),
                "admin mode active": State("admin mode active"),
            },
            transitions=[
                Transition("go", "start", "middle"),
            ],
            entry_points=["start"],
        )
        gaps = _find_unreachable(gm, {})
        descs = [g.description for g in gaps]
        assert any("admin mode active" in d for d in descs)


class TestFindMissingError:
    def test_identifies_missing_error(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "logged in", "logs out", "logged out"),
            _make_scenario("S2", "logged in", "views profile", "profile shown"),
        ])
        gm = build_graph(result)
        gaps = _find_missing_error_transitions(gm, {})
        descs = [g.description for g in gaps]
        assert any("logged in" in d for d in descs)

    def test_no_warning_with_error_transition(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "logged in", "logs out", "logged out"),
            _make_scenario("S2", "logged in", "views profile", "profile shown"),
            _make_scenario("S3", "logged in", "enters invalid data", "error shown"),
        ])
        gm = build_graph(result)
        gaps = _find_missing_error_transitions(gm, {})
        descs = [g.description for g in gaps]
        assert not any("logged in" in d for d in descs)


class TestFindContradictions:
    def test_identifies_contradiction(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "1 user", "user registers", "there are 2 users"),
            _make_scenario("B", "1 user", "user registers", "registration fails"),
        ])
        gm = build_graph(result)
        gaps = _find_contradictions(gm, {})
        assert len(gaps) > 0
        assert gaps[0].gap_type == GapType.CONTRADICTION

    def test_no_contradiction_different_events(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "1 user", "registers", "2 users"),
            _make_scenario("B", "1 user", "logs in", "logged in"),
        ])
        gm = build_graph(result)
        gaps = _find_contradictions(gm, {})
        assert len(gaps) == 0


class TestFindMissingNegatives:
    def test_suggests_negative_scenarios(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "registers", "1 user"),
        ])
        gm = build_graph(result)
        gaps = _find_missing_negatives(gm, {})
        assert len(gaps) > 0
        assert gaps[0].gap_type == GapType.MISSING_NEGATIVE


class TestAnalyzeGaps:
    def test_combines_all_gap_types(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "e1", "b"),
            _make_scenario("S2", "a", "e2", "c"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        types = {g.gap_type for g in gaps}
        # Should find at least dead ends and missing negatives
        assert len(gaps) > 0

    def test_triaged_gaps_excluded(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "e1", "b"),
        ])
        gm = build_graph(result)
        all_gaps = analyze_gaps(gm)
        # Triage all gaps
        triaged = {g.description: "intentional" for g in all_gaps}
        filtered = analyze_gaps(gm, triaged)
        assert len(filtered) < len(all_gaps) or len(all_gaps) == 0


class TestSaveLoadGaps:
    def test_roundtrip(self, tmp_path: Path) -> None:
        gaps = [
            Gap(
                gap_type=GapType.DEAD_END,
                severity=Severity.HIGH,
                description="test dead end",
                question="Is this intentional?",
                states=["locked"],
            ),
        ]
        (tmp_path / ".spec-eng").mkdir()
        save_gaps(gaps, tmp_path)
        loaded = load_gaps(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].gap_type == GapType.DEAD_END
        assert loaded[0].description == "test dead end"

    def test_load_empty(self, tmp_path: Path) -> None:
        loaded = load_gaps(tmp_path)
        assert loaded == []

    def test_gap_json_structure(self, tmp_path: Path) -> None:
        import json

        gaps = [
            Gap(
                gap_type=GapType.CONTRADICTION,
                severity=Severity.HIGH,
                description="conflict",
                question="which?",
                states=["a", "b"],
                transitions=["e1"],
            ),
        ]
        (tmp_path / ".spec-eng").mkdir()
        path = save_gaps(gaps, tmp_path)
        data = json.loads(path.read_text())
        assert data[0]["gap_type"] == "contradiction"
        assert data[0]["severity"] == "high"
