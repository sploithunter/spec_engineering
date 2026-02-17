"""Tests for MCP server tools."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec_eng.mcp_server import (
    _analyze_spec_gaps,
    _build_state_graph,
    _check_guardian,
    _detect_project,
    _export_graph,
    _find_equivalences,
    _get_project_status,
    _parse_gwt,
)

SAMPLE_GWT = """\
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with email and password.

THEN there is 1 registered user.
"""

MULTI_GWT = """\
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

;===============================================================
; User can log out.
;===============================================================
GIVEN the user is logged in.

WHEN the user logs out.

THEN the user is logged out.
"""

LEAKY_GWT = """\
;===============================================================
; UserService handles registration.
;===============================================================
GIVEN no rows in the users table.

WHEN a POST request to /api/users is sent.

THEN the database has 1 row.
"""


class TestParseGwt:
    def test_parse_from_content(self) -> None:
        result = _parse_gwt(content=SAMPLE_GWT)
        assert result["is_success"] is True
        assert result["scenario_count"] == 1
        assert result["scenarios"][0]["title"] == "User can register with email and password."

    def test_parse_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.gwt"
        f.write_text(SAMPLE_GWT)
        result = _parse_gwt(file_path=str(f))
        assert result["is_success"] is True
        assert result["scenario_count"] == 1

    def test_parse_no_input(self) -> None:
        result = _parse_gwt()
        assert "error" in result

    def test_parse_clauses_serialized(self) -> None:
        result = _parse_gwt(content=SAMPLE_GWT)
        scenario = result["scenarios"][0]
        assert len(scenario["givens"]) == 1
        assert scenario["givens"][0]["text"] == "no registered users"
        assert len(scenario["whens"]) == 1
        assert len(scenario["thens"]) == 1
        assert scenario["is_valid"] is True


class TestBuildStateGraph:
    def test_build_from_content(self) -> None:
        result = _build_state_graph(content=MULTI_GWT)
        assert "states" in result
        assert "transitions" in result
        assert "entry_points" in result
        assert "terminal_states" in result
        assert len(result["states"]) > 0
        assert len(result["transitions"]) > 0

    def test_build_no_input(self) -> None:
        result = _build_state_graph()
        assert "error" in result

    def test_build_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.gwt"
        f.write_text(MULTI_GWT)
        result = _build_state_graph(file_path=str(f))
        assert "states" in result

    def test_entry_and_terminal(self) -> None:
        result = _build_state_graph(content=MULTI_GWT)
        assert "no registered users" in result["entry_points"]
        assert "the user is logged out" in result["terminal_states"]


class TestAnalyzeSpecGaps:
    def test_gaps_found(self) -> None:
        result = _analyze_spec_gaps(content=MULTI_GWT)
        assert "gap_count" in result
        assert "gaps" in result
        assert isinstance(result["gaps"], list)

    def test_gaps_no_input(self) -> None:
        result = _analyze_spec_gaps()
        assert "error" in result

    def test_gap_structure(self) -> None:
        result = _analyze_spec_gaps(content=MULTI_GWT)
        if result["gap_count"] > 0:
            gap = result["gaps"][0]
            assert "type" in gap
            assert "severity" in gap
            assert "description" in gap
            assert "question" in gap


class TestCheckGuardian:
    def test_clean_spec(self) -> None:
        result = _check_guardian(content=SAMPLE_GWT)
        assert result["clean"] is True
        assert result["warning_count"] == 0

    def test_leaky_spec(self) -> None:
        result = _check_guardian(content=LEAKY_GWT)
        assert result["clean"] is False
        assert result["warning_count"] > 0
        categories = {w["category"] for w in result["warnings"]}
        assert len(categories) > 0

    def test_no_input(self) -> None:
        result = _check_guardian()
        assert "error" in result

    def test_sensitivity(self) -> None:
        result_low = _check_guardian(content=LEAKY_GWT, sensitivity="low")
        result_high = _check_guardian(content=LEAKY_GWT, sensitivity="high")
        assert result_high["warning_count"] >= result_low["warning_count"]


class TestFindEquivalences:
    def test_with_similar_states(self) -> None:
        gwt = """\
;===============================================================
; Scenario A.
;===============================================================
GIVEN a user is registered.
WHEN the user logs in.
THEN the user is logged in.

;===============================================================
; Scenario B.
;===============================================================
GIVEN the user is registered.
WHEN the user signs in.
THEN the user is signed in.
"""
        result = _find_equivalences(content=gwt, threshold=0.6)
        assert "equivalences" in result
        assert "count" in result

    def test_no_input(self) -> None:
        result = _find_equivalences()
        assert "error" in result


class TestExportGraph:
    def test_export_json(self) -> None:
        result = _export_graph(content=MULTI_GWT, format="json")
        assert result["format"] == "json"
        parsed = json.loads(result["output"])
        assert "states" in parsed

    def test_export_dot(self) -> None:
        result = _export_graph(content=MULTI_GWT, format="dot")
        assert result["format"] == "dot"
        assert "digraph" in result["output"]

    def test_no_input(self) -> None:
        result = _export_graph()
        assert "error" in result


class TestDetectProject:
    def test_detect_python(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        result = _detect_project(project_root=str(tmp_path))
        assert "python" in result["languages"]
        assert result["primary_language"] == "python"

    def test_detect_empty(self, tmp_path: Path) -> None:
        result = _detect_project(project_root=str(tmp_path))
        assert result["languages"] == []
        assert result["primary_language"] == ""


class TestGetProjectStatus:
    def test_uninitialized(self, tmp_path: Path) -> None:
        result = _get_project_status(project_root=str(tmp_path))
        assert result["initialized"] is False
        assert result["spec_files"] == 0

    def test_with_specs(self, tmp_path: Path) -> None:
        spec_eng_dir = tmp_path / ".spec-eng"
        spec_eng_dir.mkdir()
        (spec_eng_dir / "config.json").write_text(json.dumps({
            "version": "0.1.0", "language": "python", "framework": "pytest",
            "guardian": {"enabled": True, "sensitivity": "medium", "allowlist": []},
            "vocabulary": [], "auto_analysis": False, "targets": {},
        }))

        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        (specs_dir / "auth.gwt").write_text(MULTI_GWT)

        result = _get_project_status(project_root=str(tmp_path))
        assert result["initialized"] is True
        assert result["spec_files"] == 1
        assert result["scenario_count"] == 3
        assert result["states"] > 0
        assert result["transitions"] > 0
