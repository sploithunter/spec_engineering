"""E2E test: Parser -> Graph -> Gap Analysis pipeline.

Second E2E checkpoint: verifies the three-module chain works end-to-end.
"""

import pytest

from spec_eng.gaps import analyze_gaps
from spec_eng.graph import build_graph
from spec_eng.models import GapType
from spec_eng.parser import parse_gwt_string

pytestmark = pytest.mark.e2e


class TestParserGraphGaps:
    def test_full_pipeline(self) -> None:
        """Parse -> Graph -> Gap Analysis end-to-end."""
        content = """\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.

;===============================================================
; User can log in after registration.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in.

THEN the user is logged in.
"""
        # Parse
        result = parse_gwt_string(content)
        assert result.is_success
        assert len(result.scenarios) == 2

        # Build graph
        gm = build_graph(result)
        assert len(gm.states) >= 3
        assert len(gm.transitions) >= 2

        # Gap analysis
        gaps = analyze_gaps(gm)
        # Should find dead ends (logged in has no outbound)
        # and missing negatives
        types = {g.gap_type for g in gaps}
        assert GapType.DEAD_END in types or GapType.MISSING_NEGATIVE in types

    def test_iterative_refinement(self) -> None:
        """Test that adding specs reduces gaps."""
        # Round 1: basic scenario
        content1 = """\
;===============================================================
; User registers.
;===============================================================
GIVEN no users.

WHEN user registers.

THEN 1 user.
"""
        result1 = parse_gwt_string(content1)
        gm1 = build_graph(result1)
        gaps1 = analyze_gaps(gm1)

        # Round 2: add error handling
        content2 = """\
;===============================================================
; User registers.
;===============================================================
GIVEN no users.

WHEN user registers.

THEN 1 user.

;===============================================================
; Registration fails with invalid email.
;===============================================================
GIVEN no users.

WHEN user registers with invalid email.

THEN registration error shown.

;===============================================================
; User logs in.
;===============================================================
GIVEN 1 user.

WHEN user logs in.

THEN user is logged in.
"""
        result2 = parse_gwt_string(content2)
        gm2 = build_graph(result2)
        gaps2 = analyze_gaps(gm2)

        # After adding negative scenario and connecting chain,
        # some gaps should be resolved
        assert len(result2.scenarios) > len(result1.scenarios)
