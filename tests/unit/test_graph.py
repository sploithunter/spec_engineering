"""Unit tests for spec_eng.graph."""

import json

import pytest

from spec_eng.exporters.dot import export_dot
from spec_eng.exporters.json_export import export_json
from spec_eng.graph import (
    build_graph,
    extract_states_and_transitions,
    find_semantic_equivalences,
    graph_to_json,
    to_networkx,
    update_graph_incremental,
)
from spec_eng.models import Clause, GraphModel, ParseResult, Scenario, State


def _make_scenario(
    title: str, given: str, when: str, then: str
) -> Scenario:
    return Scenario(
        title=title,
        givens=[Clause("GIVEN", given, 1)],
        whens=[Clause("WHEN", when, 3)],
        thens=[Clause("THEN", then, 5)],
    )


class TestExtractStatesAndTransitions:
    def test_basic_extraction(self) -> None:
        s = _make_scenario("Test", "no users", "user registers", "1 user")
        states, transitions = extract_states_and_transitions(s)
        labels = {st.label for st in states}
        assert "no users" in labels
        assert "1 user" in labels
        assert len(transitions) == 1
        assert transitions[0].from_state == "no users"
        assert transitions[0].to_state == "1 user"

    def test_multiple_thens(self) -> None:
        s = Scenario(
            title="Test",
            givens=[Clause("GIVEN", "no users", 1)],
            whens=[Clause("WHEN", "user registers", 3)],
            thens=[
                Clause("THEN", "1 user", 5),
                Clause("THEN", "email sent", 6),
            ],
        )
        states, transitions = extract_states_and_transitions(s)
        assert len(transitions) == 2

    def test_source_scenario_tracked(self) -> None:
        s = _make_scenario("My Scenario", "a", "b", "c")
        _, transitions = extract_states_and_transitions(s)
        assert transitions[0].source_scenario == "My Scenario"


class TestBuildGraph:
    def test_single_scenario(self) -> None:
        result = ParseResult(
            scenarios=[_make_scenario("S1", "no users", "register", "1 user")]
        )
        gm = build_graph(result)
        assert "no users" in gm.states
        assert "1 user" in gm.states
        assert len(gm.transitions) == 1

    def test_state_merging(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
            _make_scenario("S2", "1 user", "login", "logged in"),
        ])
        gm = build_graph(result)
        # "1 user" appears in both scenarios, should be merged
        state = gm.states["1 user"]
        assert len(state.source_scenarios) == 2

    def test_entry_points(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
            _make_scenario("S2", "1 user", "login", "logged in"),
        ])
        gm = build_graph(result)
        assert "no users" in gm.entry_points

    def test_terminal_states(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
            _make_scenario("S2", "1 user", "login", "logged in"),
        ])
        gm = build_graph(result)
        assert "logged in" in gm.terminal_states

    def test_connected_path(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
            _make_scenario("S2", "1 user", "login", "logged in"),
        ])
        gm = build_graph(result)
        # Full path: no users -> register -> 1 user -> login -> logged in
        events = [t.event for t in gm.transitions]
        assert "register" in events
        assert "login" in events

    def test_cycle_detection(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "state X", "event 1", "state Y"),
            _make_scenario("S2", "state Y", "event 2", "state X"),
        ])
        gm = build_graph(result)
        assert len(gm.cycles) > 0

    def test_aggregates_multiple_files(self) -> None:
        scenarios = [
            _make_scenario(f"S{i}", f"state_{i}", f"event_{i}", f"state_{i+1}")
            for i in range(10)
        ]
        result = ParseResult(scenarios=scenarios)
        gm = build_graph(result)
        assert len(gm.transitions) == 10

    def test_empty_result(self) -> None:
        gm = build_graph(ParseResult())
        assert len(gm.states) == 0


class TestSemanticEquivalences:
    def test_exact_match_after_normalization(self) -> None:
        gm = GraphModel(states={
            "there is 1 registered user": State("there is 1 registered user"),
            "1 registered user": State("1 registered user"),
        })
        equivs = find_semantic_equivalences(gm)
        assert len(equivs) > 0
        labels = [(a, b) for a, b, _ in equivs]
        assert any(
            ("1 registered user" in a and "there is 1 registered user" in b)
            or ("there is 1 registered user" in a and "1 registered user" in b)
            for a, b in labels
        )

    def test_no_false_positives(self) -> None:
        gm = GraphModel(states={
            "no users": State("no users"),
            "logged in": State("logged in"),
        })
        equivs = find_semantic_equivalences(gm)
        assert len(equivs) == 0


class TestToNetworkx:
    def test_converts(self) -> None:
        result = ParseResult(
            scenarios=[_make_scenario("S1", "a", "event", "b")]
        )
        gm = build_graph(result)
        nxg = to_networkx(gm)
        assert "a" in nxg.nodes
        assert "b" in nxg.nodes
        assert nxg.has_edge("a", "b")


class TestIncrementalUpdate:
    def test_adds_new_scenarios(self) -> None:
        existing = build_graph(ParseResult(
            scenarios=[_make_scenario("S1", "a", "e1", "b")]
        ))
        new_scenarios = [
            _make_scenario("S2", "b", "e2", "c"),
            _make_scenario("S3", "c", "e3", "d"),
        ]
        updated = update_graph_incremental(existing, new_scenarios, "new.gwt")
        assert len(updated.transitions) == 3


class TestExports:
    def test_dot_export(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
        ])
        gm = build_graph(result)
        dot = export_dot(gm)
        assert "digraph" in dot
        assert "no users" in dot
        assert "1 user" in dot
        assert "register" in dot

    def test_dot_entry_distinguished(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
        ])
        gm = build_graph(result)
        dot = export_dot(gm)
        assert "doublecircle" in dot

    def test_dot_terminal_distinguished(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
        ])
        gm = build_graph(result)
        dot = export_dot(gm)
        assert "bold" in dot

    def test_json_export(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
        ])
        gm = build_graph(result)
        j = export_json(gm)
        data = json.loads(j)
        assert "states" in data
        assert "transitions" in data
        assert "entry_points" in data
        assert "terminal_states" in data

    def test_json_has_source_refs(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("S1", "no users", "register", "1 user"),
        ])
        gm = build_graph(result)
        data = graph_to_json(gm)
        # States have source references
        assert "S1" in data["states"]["no users"]["source_scenarios"]
        # Transitions have source references
        assert data["transitions"][0]["source_scenario"] == "S1"
