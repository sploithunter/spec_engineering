"""E2E test: Parser -> Graph pipeline.

First E2E checkpoint: verifies that parsing GWT content and building
a state machine graph works end-to-end.
"""

import pytest

from spec_eng.graph import build_graph, graph_to_json
from spec_eng.parser import parse_gwt_string

pytestmark = pytest.mark.e2e


class TestParserToGraph:
    def test_parse_and_build_graph(self, multi_scenario_gwt: str) -> None:
        """Parse multi-scenario GWT -> build graph -> verify structure."""
        result = parse_gwt_string(multi_scenario_gwt)
        assert result.is_success
        assert len(result.scenarios) == 3

        gm = build_graph(result)

        # Verify states
        assert "no registered users" in gm.states
        assert "there is 1 registered user" in gm.states
        assert "the user is logged in" in gm.states
        assert "the user is logged out" in gm.states

        # Verify connected path exists
        events = {t.event for t in gm.transitions}
        assert "a user registers" in events
        assert "the user logs in" in events
        assert "the user logs out" in events

        # Entry point
        assert "no registered users" in gm.entry_points

    def test_full_pipeline_to_json(self, multi_scenario_gwt: str) -> None:
        """Parse -> graph -> JSON export end-to-end."""
        result = parse_gwt_string(multi_scenario_gwt)
        gm = build_graph(result)
        data = graph_to_json(gm)

        assert len(data["states"]) >= 4
        assert len(data["transitions"]) >= 3
        assert len(data["entry_points"]) >= 1
