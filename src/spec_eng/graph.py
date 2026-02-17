"""State machine extraction from parsed GWT scenarios."""

from __future__ import annotations

from difflib import SequenceMatcher

import networkx as nx

from spec_eng.models import GraphModel, ParseResult, Scenario, State, Transition


def extract_states_and_transitions(
    scenario: Scenario,
) -> tuple[list[State], list[Transition]]:
    """Extract states and transitions from a single scenario.

    GIVEN clauses define precondition states.
    WHEN clauses define transition events.
    THEN clauses define postcondition states.

    For each (GIVEN, WHEN) pair, we create transitions to each THEN state.
    """
    states: list[State] = []
    transitions: list[Transition] = []

    # Precondition states from GIVENs
    given_labels = [g.text for g in scenario.givens]
    for label in given_labels:
        states.append(State(label=label, source_scenarios=(scenario.title,)))

    # Postcondition states from THENs
    then_labels = [t.text for t in scenario.thens]
    for label in then_labels:
        states.append(State(label=label, source_scenarios=(scenario.title,)))

    # Transitions: each WHEN event connects GIVENs to THENs
    for when_clause in scenario.whens:
        for given_label in given_labels:
            for then_label in then_labels:
                transitions.append(Transition(
                    event=when_clause.text,
                    from_state=given_label,
                    to_state=then_label,
                    source_scenario=scenario.title,
                ))

    return states, transitions


def build_graph(parse_result: ParseResult) -> GraphModel:
    """Build a GraphModel from parsed scenarios."""
    all_states: dict[str, State] = {}
    all_transitions: list[Transition] = []

    for scenario in parse_result.scenarios:
        states, transitions = extract_states_and_transitions(scenario)

        for state in states:
            if state.label in all_states:
                # Merge source scenarios
                existing = all_states[state.label]
                merged_sources = tuple(
                    sorted(set(existing.source_scenarios + state.source_scenarios))
                )
                all_states[state.label] = State(
                    label=state.label, source_scenarios=merged_sources
                )
            else:
                all_states[state.label] = state

        all_transitions.extend(transitions)

    # Identify entry points: states that appear as GIVEN but never as THEN
    then_labels = {t.to_state for t in all_transitions}
    given_labels = {t.from_state for t in all_transitions}
    entry_points = sorted(given_labels - then_labels)

    # Identify terminal states: states that appear as THEN but never as GIVEN
    terminal_states = sorted(then_labels - given_labels)

    # Detect cycles using networkx
    nxg = _to_networkx_internal(all_states, all_transitions)
    cycles = [sorted(c) for c in nx.simple_cycles(nxg)]

    return GraphModel(
        states=all_states,
        transitions=all_transitions,
        entry_points=entry_points,
        terminal_states=terminal_states,
        cycles=cycles,
    )


def find_semantic_equivalences(
    graph: GraphModel, threshold: float = 0.7
) -> list[tuple[str, str, float]]:
    """Find pairs of state labels that may be semantically equivalent.

    Returns list of (label_a, label_b, similarity_score) tuples.
    """
    labels = sorted(graph.states.keys())
    equivalences: list[tuple[str, str, float]] = []

    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            # Normalize for comparison
            norm_a = _normalize_label(a)
            norm_b = _normalize_label(b)
            if norm_a == norm_b:
                equivalences.append((a, b, 1.0))
                continue
            score = SequenceMatcher(None, norm_a, norm_b).ratio()
            if score >= threshold:
                equivalences.append((a, b, round(score, 2)))

    return equivalences


def to_networkx(graph: GraphModel) -> nx.DiGraph:
    """Convert GraphModel to a NetworkX DiGraph."""
    return _to_networkx_internal(graph.states, graph.transitions)


def update_graph_incremental(
    existing: GraphModel, new_scenarios: list[Scenario], source_file: str
) -> GraphModel:
    """Update a graph by replacing scenarios from a single source file."""
    # Remove transitions from the modified file
    remaining_transitions = [
        t for t in existing.transitions
        if t.source_scenario not in {s.title for s in new_scenarios}
    ]

    # Build a temporary parse result for the new scenarios
    temp = ParseResult(scenarios=new_scenarios)
    new_graph = build_graph(temp)

    # Merge
    merged_states = dict(existing.states)
    for label, state in new_graph.states.items():
        merged_states[label] = state

    all_transitions = remaining_transitions + new_graph.transitions

    # Recalculate entry/terminal/cycles
    then_labels = {t.to_state for t in all_transitions}
    given_labels = {t.from_state for t in all_transitions}
    entry_points = sorted(given_labels - then_labels)
    terminal_states = sorted(then_labels - given_labels)

    nxg = _to_networkx_internal(merged_states, all_transitions)
    cycles = [sorted(c) for c in nx.simple_cycles(nxg)]

    return GraphModel(
        states=merged_states,
        transitions=all_transitions,
        entry_points=entry_points,
        terminal_states=terminal_states,
        cycles=cycles,
    )


def graph_to_json(graph: GraphModel) -> dict:
    """Export GraphModel as a JSON-serializable dictionary."""
    return {
        "states": {
            label: {
                "label": label,
                "source_scenarios": list(state.source_scenarios),
            }
            for label, state in graph.states.items()
        },
        "transitions": [
            {
                "event": t.event,
                "from_state": t.from_state,
                "to_state": t.to_state,
                "source_scenario": t.source_scenario,
            }
            for t in graph.transitions
        ],
        "entry_points": graph.entry_points,
        "terminal_states": graph.terminal_states,
        "cycles": graph.cycles,
    }


def _to_networkx_internal(
    states: dict[str, State], transitions: list[Transition]
) -> nx.DiGraph:
    """Build a networkx DiGraph from states and transitions."""
    g: nx.DiGraph[str] = nx.DiGraph()
    for label in states:
        g.add_node(label)
    for t in transitions:
        g.add_edge(t.from_state, t.to_state, event=t.event)
    return g


def _normalize_label(label: str) -> str:
    """Normalize a state label for comparison."""
    words = label.lower().split()
    # Remove articles and common filler words
    stop = {"a", "an", "the", "is", "are", "has", "have", "there"}
    return " ".join(w for w in words if w not in stop)
