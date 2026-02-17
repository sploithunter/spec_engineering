"""Unit tests for spec_eng.parser."""

from pathlib import Path

import pytest

from spec_eng.parser import Lexer, Parser, TokenType, parse_gwt_file, parse_gwt_string


# ── Lexer Tests ──────────────────────────────────────────────────────


class TestLexer:
    def test_tokenize_header_bar(self) -> None:
        content = ";==============================================================="
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.HEADER_BAR

    def test_tokenize_comment(self) -> None:
        content = "; This is a comment."
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.COMMENT
        assert tokens[0].text == "This is a comment."

    def test_tokenize_given(self) -> None:
        content = "GIVEN no registered users."
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.GIVEN
        assert tokens[0].text == "no registered users"

    def test_tokenize_when(self) -> None:
        content = "WHEN a user registers."
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.WHEN
        assert tokens[0].text == "a user registers"

    def test_tokenize_then(self) -> None:
        content = "THEN there is 1 registered user."
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.THEN
        assert tokens[0].text == "there is 1 registered user"

    def test_tokenize_blank(self) -> None:
        content = "\n\n"
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.BLANK

    def test_tokenize_eof(self) -> None:
        tokens = Lexer("").tokenize()
        assert tokens[-1].type == TokenType.EOF

    def test_multiline_clause(self) -> None:
        content = "GIVEN a user with email\n  \"bob@example.com\"."
        tokens = Lexer(content).tokenize()
        assert tokens[0].type == TokenType.GIVEN
        assert '"bob@example.com"' in tokens[0].text

    def test_line_numbers(self) -> None:
        content = "GIVEN x.\n\nWHEN y.\n\nTHEN z."
        tokens = Lexer(content).tokenize()
        given = [t for t in tokens if t.type == TokenType.GIVEN][0]
        when = [t for t in tokens if t.type == TokenType.WHEN][0]
        then = [t for t in tokens if t.type == TokenType.THEN][0]
        assert given.line_number == 1
        assert when.line_number == 3
        assert then.line_number == 5

    def test_full_scenario_tokens(self, sample_gwt_content: str) -> None:
        tokens = Lexer(sample_gwt_content).tokenize()
        types = [t.type for t in tokens]
        assert TokenType.HEADER_BAR in types
        assert TokenType.COMMENT in types
        assert TokenType.GIVEN in types
        assert TokenType.WHEN in types
        assert TokenType.THEN in types
        assert types[-1] == TokenType.EOF


# ── Parser Tests ─────────────────────────────────────────────────────


class TestParser:
    def test_parse_single_scenario(self, sample_gwt_content: str) -> None:
        result = parse_gwt_string(sample_gwt_content)
        assert result.is_success
        assert len(result.scenarios) == 1

    def test_scenario_title(self, sample_gwt_content: str) -> None:
        result = parse_gwt_string(sample_gwt_content)
        assert result.scenarios[0].title == "User can register with email and password."

    def test_scenario_givens(self, sample_gwt_content: str) -> None:
        result = parse_gwt_string(sample_gwt_content)
        s = result.scenarios[0]
        assert len(s.givens) == 1
        assert s.givens[0].text == "no registered users"

    def test_scenario_whens(self, sample_gwt_content: str) -> None:
        result = parse_gwt_string(sample_gwt_content)
        s = result.scenarios[0]
        assert len(s.whens) == 1
        assert 'email "bob@example.com"' in s.whens[0].text

    def test_scenario_thens(self, sample_gwt_content: str) -> None:
        result = parse_gwt_string(sample_gwt_content)
        s = result.scenarios[0]
        assert len(s.thens) == 2
        assert s.thens[0].text == "there is 1 registered user"

    def test_multiple_scenarios(self, multi_scenario_gwt: str) -> None:
        result = parse_gwt_string(multi_scenario_gwt)
        assert result.is_success
        assert len(result.scenarios) == 3

    def test_multiple_scenario_titles(self, multi_scenario_gwt: str) -> None:
        result = parse_gwt_string(multi_scenario_gwt)
        titles = [s.title for s in result.scenarios]
        assert "User can register." in titles
        assert "User can log in after registration." in titles
        assert "User can log out." in titles

    def test_each_scenario_independent(self, multi_scenario_gwt: str) -> None:
        result = parse_gwt_string(multi_scenario_gwt)
        for s in result.scenarios:
            assert s.is_valid

    def test_missing_when_clause(self) -> None:
        content = """\
;===============================================================
; Bad scenario.
;===============================================================
GIVEN something.

THEN a result.
"""
        result = parse_gwt_string(content)
        assert not result.is_success
        assert any("WHEN" in e.message for e in result.errors)

    def test_missing_given_clause(self) -> None:
        content = """\
;===============================================================
; Bad scenario.
;===============================================================
WHEN something.

THEN a result.
"""
        result = parse_gwt_string(content)
        assert not result.is_success
        assert any("GIVEN" in e.message for e in result.errors)

    def test_missing_then_clause(self) -> None:
        content = """\
;===============================================================
; Bad scenario.
;===============================================================
GIVEN something.

WHEN action.
"""
        result = parse_gwt_string(content)
        assert not result.is_success
        assert any("THEN" in e.message for e in result.errors)

    def test_empty_file(self) -> None:
        result = parse_gwt_string("")
        assert result.is_success
        assert len(result.scenarios) == 0

    def test_blank_lines_only(self) -> None:
        result = parse_gwt_string("\n\n\n")
        assert result.is_success
        assert len(result.scenarios) == 0

    def test_source_file_tracking(self) -> None:
        content = """\
;===============================================================
; Test.
;===============================================================
GIVEN x.

WHEN y.

THEN z.
"""
        result = parse_gwt_string(content, source_file="test.gwt")
        assert result.scenarios[0].source_file == "test.gwt"

    def test_error_includes_file_and_line(self) -> None:
        content = """\
;===============================================================
; Bad.
;===============================================================
GIVEN x.

THEN z.
"""
        result = parse_gwt_string(content, source_file="bad.gwt")
        assert len(result.errors) > 0
        assert result.errors[0].source_file == "bad.gwt"
        assert result.errors[0].line_number > 0

    def test_multiple_givens(self) -> None:
        content = """\
;===============================================================
; Multi-given scenario.
;===============================================================
GIVEN a registered user.
GIVEN the user is not logged in.

WHEN the user logs in.

THEN the user is logged in.
"""
        result = parse_gwt_string(content)
        assert result.is_success
        assert len(result.scenarios[0].givens) == 2

    def test_multiple_thens(self) -> None:
        content = """\
;===============================================================
; Multi-then scenario.
;===============================================================
GIVEN no users.

WHEN a user registers.

THEN there is 1 user.
THEN the user can log in.
THEN a welcome email is sent.
"""
        result = parse_gwt_string(content)
        assert result.is_success
        assert len(result.scenarios[0].thens) == 3

    def test_parse_file(self, sample_gwt_file: Path) -> None:
        result = parse_gwt_file(sample_gwt_file)
        assert result.is_success
        assert len(result.scenarios) == 1
        assert result.scenarios[0].source_file == str(sample_gwt_file)
