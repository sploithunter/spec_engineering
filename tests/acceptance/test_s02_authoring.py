"""Acceptance tests for Section 2: GWT Spec Authoring.

Covers: 2.3, 2.4, 2.6 (parser-related). 2.1 tested in test_s01. 2.2 tested in Phase 7.
"""

import pytest

from spec_eng.parser import parse_gwt_string

pytestmark = pytest.mark.acceptance


class TestScenario2_3:
    """2.3: GWT files follow the required format."""

    def test_single_scenario_extracted(self) -> None:
        content = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios) == 1

    def test_one_given_clause(self) -> None:
        content = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios[0].givens) == 1

    def test_one_when_clause(self) -> None:
        content = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios[0].whens) == 1

    def test_two_then_clauses(self) -> None:
        content = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios[0].thens) == 2

    def test_scenario_title(self) -> None:
        content = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email "bob@example.com" and password "secret123".

THEN there is 1 registered user.
THEN the user "bob@example.com" can log in.
"""
        result = parse_gwt_string(content)
        assert result.scenarios[0].title == "User can register with email and password."


class TestScenario2_4:
    """2.4: Multiple scenarios in one file are parsed independently."""

    def test_three_scenarios(self) -> None:
        content = """\
;===============================================================
; Scenario one.
;===============================================================
GIVEN state A.

WHEN event 1.

THEN state B.

;===============================================================
; Scenario two.
;===============================================================
GIVEN state B.

WHEN event 2.

THEN state C.

;===============================================================
; Scenario three.
;===============================================================
GIVEN state C.

WHEN event 3.

THEN state D.
"""
        result = parse_gwt_string(content)
        assert len(result.scenarios) == 3

    def test_each_has_own_title(self) -> None:
        content = """\
;===============================================================
; Scenario one.
;===============================================================
GIVEN a.

WHEN b.

THEN c.

;===============================================================
; Scenario two.
;===============================================================
GIVEN d.

WHEN e.

THEN f.

;===============================================================
; Scenario three.
;===============================================================
GIVEN g.

WHEN h.

THEN i.
"""
        result = parse_gwt_string(content)
        titles = [s.title for s in result.scenarios]
        assert titles == ["Scenario one.", "Scenario two.", "Scenario three."]


class TestScenario2_6:
    """2.6: Invalid GWT syntax is rejected with a helpful error."""

    def test_missing_when_fails(self) -> None:
        content = """\
;===============================================================
; Missing when.
;===============================================================
GIVEN something.

THEN a result.
"""
        result = parse_gwt_string(content, source_file="bad.gwt")
        assert not result.is_success

    def test_error_identifies_file(self) -> None:
        content = """\
;===============================================================
; Missing when.
;===============================================================
GIVEN something.

THEN a result.
"""
        result = parse_gwt_string(content, source_file="bad.gwt")
        assert result.errors[0].source_file == "bad.gwt"

    def test_error_identifies_line(self) -> None:
        content = """\
;===============================================================
; Missing when.
;===============================================================
GIVEN something.

THEN a result.
"""
        result = parse_gwt_string(content, source_file="bad.gwt")
        assert result.errors[0].line_number > 0

    def test_error_explains_requirement(self) -> None:
        content = """\
;===============================================================
; Missing when.
;===============================================================
GIVEN something.

THEN a result.
"""
        result = parse_gwt_string(content, source_file="bad.gwt")
        msg = result.errors[0].message.lower()
        assert "when" in msg
