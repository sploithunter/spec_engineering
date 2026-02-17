"""Gap analysis engine for state machine graphs."""

from __future__ import annotations

import json
from pathlib import Path

from spec_eng.models import Gap, GapType, GraphModel, Severity, Transition


def analyze_gaps(graph: GraphModel, triaged: dict[str, str] | None = None) -> list[Gap]:
    """Analyze a GraphModel for completeness gaps.

    Args:
        graph: The state machine graph to analyze.
        triaged: Dict mapping gap descriptions to triage status
                 ("intentional", "out-of-scope"). These are excluded.

    Returns:
        List of Gap objects found.
    """
    triaged = triaged or {}
    gaps: list[Gap] = []

    gaps.extend(_find_dead_ends(graph, triaged))
    gaps.extend(_find_unreachable(graph, triaged))
    gaps.extend(_find_missing_error_transitions(graph, triaged))
    gaps.extend(_find_contradictions(graph, triaged))
    gaps.extend(_find_missing_negatives(graph, triaged))

    return gaps


def _find_dead_ends(graph: GraphModel, triaged: dict[str, str]) -> list[Gap]:
    """Find states with no outbound transitions (potential dead ends)."""
    gaps: list[Gap] = []
    outbound: set[str] = {t.from_state for t in graph.transitions}

    for label in graph.states:
        if label not in outbound and label in {t.to_state for t in graph.transitions}:
            desc = f'State "{label}" has no outbound transitions'
            if desc in triaged:
                continue
            gaps.append(Gap(
                gap_type=GapType.DEAD_END,
                severity=Severity.MEDIUM,
                description=desc,
                question="Is this an intentional terminal state?",
                states=[label],
            ))

    return gaps


def _find_unreachable(graph: GraphModel, triaged: dict[str, str]) -> list[Gap]:
    """Find states with no inbound transitions from entry points."""
    gaps: list[Gap] = []
    inbound: set[str] = {t.to_state for t in graph.transitions}

    for label in graph.states:
        if label not in inbound and label not in graph.entry_points:
            # Not reachable and not an entry point
            # Check if it appears as a from_state (it would be an orphan entry)
            if label in {t.from_state for t in graph.transitions}:
                continue  # It's used as a source, just not reachable from declared entries
            desc = f'State "{label}" has no inbound transitions from any entry point'
            if desc in triaged:
                continue
            gaps.append(Gap(
                gap_type=GapType.UNREACHABLE,
                severity=Severity.HIGH,
                description=desc,
                question="How does the system reach this state?",
                states=[label],
            ))

    return gaps


def _find_missing_error_transitions(
    graph: GraphModel, triaged: dict[str, str]
) -> list[Gap]:
    """Find states that handle some events but have no error transition."""
    gaps: list[Gap] = []

    # Group transitions by from_state
    state_events: dict[str, list[str]] = {}
    for t in graph.transitions:
        state_events.setdefault(t.from_state, []).append(t.event)

    for state, events in state_events.items():
        # If a state has multiple transitions, check if any could be error-like
        has_error = any(
            "error" in e.lower() or "fail" in e.lower() or "invalid" in e.lower()
            for e in events
        )
        if not has_error and len(events) >= 2:
            desc = (
                f'State "{state}" handles {len(events)} events '
                f'but has no error transition'
            )
            if desc in triaged:
                continue
            gaps.append(Gap(
                gap_type=GapType.MISSING_ERROR,
                severity=Severity.LOW,
                description=desc,
                question=f"What happens when a {state} encounters an error?",
                states=[state],
                transitions=events,
            ))

    return gaps


def _find_contradictions(graph: GraphModel, triaged: dict[str, str]) -> list[Gap]:
    """Find cases where same precondition+event leads to different outcomes."""
    gaps: list[Gap] = []

    # Group by (from_state, event)
    groups: dict[tuple[str, str], list[Transition]] = {}
    for t in graph.transitions:
        key = (t.from_state, t.event)
        groups.setdefault(key, []).append(t)

    for (from_state, event), transitions in groups.items():
        to_states = {t.to_state for t in transitions}
        if len(to_states) > 1:
            desc = (
                f'Contradiction: "{from_state}" + "{event}" leads to '
                f'{len(to_states)} different outcomes'
            )
            if desc in triaged:
                continue
            scenarios = [t.source_scenario for t in transitions if t.source_scenario]
            gaps.append(Gap(
                gap_type=GapType.CONTRADICTION,
                severity=Severity.HIGH,
                description=desc,
                question=(
                    "These scenarios have the same precondition and event "
                    "but different outcomes. Is there a missing condition?"
                ),
                states=[from_state] + sorted(to_states),
                transitions=[f"{event} (from {s})" for s in scenarios],
            ))

    return gaps


def _find_missing_negatives(
    graph: GraphModel, triaged: dict[str, str]
) -> list[Gap]:
    """Suggest negative scenarios for states with only positive transitions."""
    gaps: list[Gap] = []

    # Group events by from_state
    state_events: dict[str, list[str]] = {}
    for t in graph.transitions:
        state_events.setdefault(t.from_state, []).append(t.event)

    for state, events in state_events.items():
        has_negative = any(
            "fail" in e.lower() or "invalid" in e.lower() or "error" in e.lower()
            or "reject" in e.lower() or "deny" in e.lower() or "not" in e.lower()
            for e in events
        )
        if not has_negative:
            suggestions: list[str] = []
            for event in events:
                suggestions.append(f"What happens when {event} fails?")
                suggestions.append(f"What happens when {event} with invalid data?")

            desc = (
                f'State "{state}" only has positive scenarios. '
                f'Missing negative cases.'
            )
            if desc in triaged:
                continue
            gaps.append(Gap(
                gap_type=GapType.MISSING_NEGATIVE,
                severity=Severity.MEDIUM,
                description=desc,
                question="\n".join(suggestions[:3]),
                states=[state],
            ))

    return gaps


def save_gaps(gaps: list[Gap], project_root: Path) -> Path:
    """Save gap report to .spec-eng/gaps.json."""
    spec_eng_dir = project_root / ".spec-eng"
    spec_eng_dir.mkdir(exist_ok=True)
    path = spec_eng_dir / "gaps.json"

    data = [
        {
            "gap_type": g.gap_type.value,
            "severity": g.severity.value,
            "description": g.description,
            "question": g.question,
            "states": g.states,
            "transitions": g.transitions,
            "triage_status": g.triage_status,
        }
        for g in gaps
    ]
    path.write_text(json.dumps(data, indent=2))
    return path


def load_gaps(project_root: Path) -> list[Gap]:
    """Load gap report from .spec-eng/gaps.json."""
    path = project_root / ".spec-eng" / "gaps.json"
    if not path.exists():
        return []

    data = json.loads(path.read_text())
    return [
        Gap(
            gap_type=GapType(g["gap_type"]),
            severity=Severity(g["severity"]),
            description=g["description"],
            question=g["question"],
            states=g.get("states", []),
            transitions=g.get("transitions", []),
            triage_status=g.get("triage_status"),
        )
        for g in data
    ]


def load_triaged(project_root: Path) -> dict[str, str]:
    """Load triaged gaps (intentional/out-of-scope) to exclude from analysis."""
    gaps = load_gaps(project_root)
    return {
        g.description: g.triage_status
        for g in gaps
        if g.triage_status in ("intentional", "out-of-scope")
    }
