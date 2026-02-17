"""JSON export for state machine graphs and IR."""

from __future__ import annotations

import json

from spec_eng.graph import graph_to_json
from spec_eng.models import GraphModel


def export_json(graph: GraphModel, indent: int = 2) -> str:
    """Export a GraphModel as a JSON string."""
    return json.dumps(graph_to_json(graph), indent=indent)
