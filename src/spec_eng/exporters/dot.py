"""Graphviz DOT export for state machine graphs."""

from __future__ import annotations

from spec_eng.models import GraphModel


def export_dot(graph: GraphModel) -> str:
    """Export a GraphModel as a Graphviz DOT string."""
    lines = ["digraph spec_state_machine {", "  rankdir=LR;", ""]

    # Entry points: double circle
    if graph.entry_points:
        entry_ids = " ".join(f'"{_escape(s)}"' for s in graph.entry_points)
        lines.append(f"  node [shape=doublecircle]; {entry_ids};")

    # Terminal states: bold box
    if graph.terminal_states:
        terminal_ids = " ".join(f'"{_escape(s)}"' for s in graph.terminal_states)
        lines.append(f"  node [shape=box, style=bold]; {terminal_ids};")

    # Default shape for other nodes
    lines.append("  node [shape=ellipse, style=solid];")
    lines.append("")

    # Edges
    for t in graph.transitions:
        from_s = _escape(t.from_state)
        to_s = _escape(t.to_state)
        event = _escape(t.event)
        lines.append(f'  "{from_s}" -> "{to_s}" [label="{event}"];')

    lines.append("}")
    return "\n".join(lines)


def _escape(text: str) -> str:
    """Escape a string for DOT format."""
    return text.replace('"', '\\"').replace("\n", "\\n")
