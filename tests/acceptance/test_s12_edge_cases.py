"""Acceptance tests for Section 12: Error Handling and Edge Cases.

Covers: 12.1 - 12.5.
"""

import time

import pytest

from spec_eng.graph import build_graph
from spec_eng.models import Clause, ParseResult, Scenario
from spec_eng.parser import parse_gwt_string

pytestmark = pytest.mark.acceptance


def _make_scenario(title: str, given: str, when: str, then: str) -> Scenario:
    return Scenario(
        title=title,
        givens=[Clause("GIVEN", given, 1)],
        whens=[Clause("WHEN", when, 3)],
        thens=[Clause("THEN", then, 5)],
    )


class TestScenario12_1:
    """12.1: Empty spec files are handled gracefully."""

    def test_empty_file_no_scenarios(self) -> None:
        result = parse_gwt_string("")
        assert len(result.scenarios) == 0

    def test_empty_file_no_error(self) -> None:
        result = parse_gwt_string("")
        assert result.is_success

    def test_comments_only_no_scenarios(self) -> None:
        content = "; Just a comment\n; Another comment\n"
        result = parse_gwt_string(content)
        assert len(result.scenarios) == 0
        assert result.is_success


class TestScenario12_2:
    """12.2: Circular state references are detected."""

    def test_cycle_represented(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "state X", "event 1", "state Y"),
            _make_scenario("B", "state Y", "event 2", "state X"),
        ])
        gm = build_graph(result)
        assert len(gm.cycles) > 0

    def test_cycle_in_metadata(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("A", "state X", "event 1", "state Y"),
            _make_scenario("B", "state Y", "event 2", "state X"),
        ])
        gm = build_graph(result)
        # Cycles should be in the graph model
        assert gm.cycles is not None

    def test_cycles_not_flagged_as_errors(self) -> None:
        from spec_eng.gaps import analyze_gaps

        result = ParseResult(scenarios=[
            _make_scenario("A", "state X", "event 1", "state Y"),
            _make_scenario("B", "state Y", "event 2", "state X"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        # No gap should specifically call out the cycle as an error
        gap_descs = [g.description.lower() for g in gaps]
        assert not any("cycle" in d for d in gap_descs)


class TestScenario12_3:
    """12.3: Very large spec suites are handled without degradation."""

    @pytest.mark.slow
    def test_large_suite_performance(self) -> None:
        # Generate 500 scenarios
        scenarios = []
        for i in range(500):
            scenarios.append(
                _make_scenario(f"S{i}", f"state_{i}", f"event_{i}", f"state_{i+1}")
            )
        result = ParseResult(scenarios=scenarios)

        start = time.time()
        gm = build_graph(result)
        elapsed = time.time() - start

        assert len(gm.transitions) == 500
        assert elapsed < 30  # Well within 30 seconds


class TestScenario12_4:
    """12.4: The tool works without an internet connection."""

    def test_parse_works_offline(self) -> None:
        content = ";===\n; Test.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        result = parse_gwt_string(content)
        assert result.is_success

    def test_graph_works_offline(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "b", "c"),
        ])
        gm = build_graph(result)
        assert len(gm.states) > 0

    def test_gaps_work_offline(self) -> None:
        from spec_eng.gaps import analyze_gaps

        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "b", "c"),
        ])
        gm = build_graph(result)
        gaps = analyze_gaps(gm)
        # Should work without network
        assert isinstance(gaps, list)


class TestScenario12_5:
    """12.5: Conflicting spec files are reported."""

    def test_duplicate_titles_both_parsed(self) -> None:
        content = """\
;===============================================================
; User can register.
;===============================================================
GIVEN no users.

WHEN user registers.

THEN there is 1 user.

;===============================================================
; User can register.
;===============================================================
GIVEN 1 user.

WHEN another user registers.

THEN there are 2 users.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios) == 2
        titles = [s.title for s in result.scenarios]
        assert titles.count("User can register.") == 2
