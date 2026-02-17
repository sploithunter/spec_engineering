"""FastMCP server exposing spec-eng tools for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from spec_eng.config import detect_framework, detect_language, is_initialized
from spec_eng.exporters.dot import export_dot
from spec_eng.exporters.json_export import export_json
from spec_eng.gaps import analyze_gaps, load_triaged
from spec_eng.graph import (
    build_graph,
    find_semantic_equivalences,
    graph_to_json,
)
from spec_eng.guardian import analyze_scenario
from spec_eng.models import ParseResult, Scenario
from spec_eng.parser import parse_gwt_file, parse_gwt_string
from spec_eng.pipeline import is_bootstrapped

mcp = FastMCP("spec-eng")


# --- Serialization helpers ---


def _serialize_scenario(scenario: Scenario) -> dict[str, Any]:
    """Serialize a Scenario to a JSON-compatible dict."""
    return {
        "title": scenario.title,
        "givens": [{"type": c.clause_type, "text": c.text, "line": c.line_number}
                   for c in scenario.givens],
        "whens": [{"type": c.clause_type, "text": c.text, "line": c.line_number}
                  for c in scenario.whens],
        "thens": [{"type": c.clause_type, "text": c.text, "line": c.line_number}
                  for c in scenario.thens],
        "source_file": scenario.source_file,
        "line_number": scenario.line_number,
        "is_valid": scenario.is_valid,
    }


def _serialize_parse_result(result: ParseResult) -> dict[str, Any]:
    """Serialize a ParseResult to a JSON-compatible dict."""
    return {
        "scenarios": [_serialize_scenario(s) for s in result.scenarios],
        "errors": [{"message": e.message, "line": e.line_number, "file": e.source_file}
                   for e in result.errors],
        "is_success": result.is_success,
        "scenario_count": len(result.scenarios),
        "error_count": len(result.errors),
    }


# --- Tool implementation functions (testable without MCP) ---


def _parse_gwt(
    content: str | None = None, file_path: str | None = None,
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}
    return _serialize_parse_result(result)


def _build_state_graph(
    content: str | None = None, file_path: str | None = None,
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}

    if not result.is_success or not result.scenarios:
        return {
            "error": "Parse failed or no scenarios found",
            "parse_errors": [{"message": e.message, "line": e.line_number}
                             for e in result.errors],
        }

    graph = build_graph(result)
    return graph_to_json(graph)


def _analyze_spec_gaps(
    content: str | None = None,
    file_path: str | None = None,
    project_root: str | None = None,
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}

    if not result.is_success or not result.scenarios:
        return {"error": "Parse failed or no scenarios found"}

    graph = build_graph(result)
    triaged: dict[str, str] = {}
    if project_root:
        triaged = load_triaged(Path(project_root))

    gaps = analyze_gaps(graph, triaged)
    return {
        "gap_count": len(gaps),
        "gaps": [
            {
                "type": g.gap_type.value,
                "severity": g.severity.value,
                "description": g.description,
                "question": g.question,
                "states": g.states,
                "transitions": g.transitions,
            }
            for g in gaps
        ],
    }


def _check_guardian(
    content: str | None = None,
    file_path: str | None = None,
    sensitivity: str = "medium",
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}

    if not result.scenarios:
        return {"warnings": [], "warning_count": 0, "clean": True}

    all_warnings = []
    for scenario in result.scenarios:
        warnings = analyze_scenario(scenario, sensitivity, allowlist)
        for w in warnings:
            all_warnings.append({
                "original_text": w.original_text,
                "flagged_terms": w.flagged_terms,
                "suggested_alternative": w.suggested_alternative,
                "category": w.category,
            })

    return {
        "warnings": all_warnings,
        "warning_count": len(all_warnings),
        "clean": len(all_warnings) == 0,
    }


def _find_equivalences(
    content: str | None = None,
    file_path: str | None = None,
    threshold: float = 0.7,
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}

    if not result.scenarios:
        return {"equivalences": [], "count": 0}

    graph = build_graph(result)
    equivs = find_semantic_equivalences(graph, threshold)
    return {
        "equivalences": [
            {"label_a": a, "label_b": b, "similarity": score}
            for a, b, score in equivs
        ],
        "count": len(equivs),
    }


def _export_graph(
    content: str | None = None,
    file_path: str | None = None,
    format: str = "json",
) -> dict[str, Any]:
    if file_path:
        result = parse_gwt_file(Path(file_path))
    elif content:
        result = parse_gwt_string(content)
    else:
        return {"error": "Provide either 'content' or 'file_path'"}

    if not result.scenarios:
        return {"error": "No scenarios to export"}

    graph = build_graph(result)

    if format == "dot":
        return {"format": "dot", "output": export_dot(graph)}
    else:
        return {"format": "json", "output": export_json(graph)}


def _detect_project(project_root: str = ".") -> dict[str, Any]:
    root = Path(project_root)
    languages = detect_language(root)
    primary = languages[0] if languages else ""
    framework = detect_framework(root, primary) if primary else ""
    return {
        "languages": languages,
        "primary_language": primary,
        "framework": framework,
    }


def _get_project_status(project_root: str = ".") -> dict[str, Any]:
    root = Path(project_root)
    status: dict[str, Any] = {
        "initialized": is_initialized(root),
        "pipeline_bootstrapped": is_bootstrapped(root),
    }

    specs_dir = root / "specs"
    if specs_dir.is_dir():
        gwt_files = list(specs_dir.glob("*.gwt"))
        status["spec_files"] = len(gwt_files)

        all_scenarios: list[Scenario] = []
        all_errors = []
        for f in gwt_files:
            r = parse_gwt_file(f)
            all_scenarios.extend(r.scenarios)
            all_errors.extend(r.errors)

        status["scenario_count"] = len(all_scenarios)
        status["parse_errors"] = len(all_errors)

        if all_scenarios:
            combined = ParseResult(scenarios=all_scenarios, errors=all_errors)
            graph = build_graph(combined)
            status["states"] = len(graph.states)
            status["transitions"] = len(graph.transitions)
            status["entry_points"] = len(graph.entry_points)
            status["terminal_states"] = len(graph.terminal_states)
            status["cycles"] = len(graph.cycles)

            triaged = load_triaged(root)
            gaps = analyze_gaps(graph, triaged)
            status["gaps"] = len(gaps)
            status["high_severity_gaps"] = sum(
                1 for g in gaps if g.severity.value == "high"
            )
    else:
        status["spec_files"] = 0
        status["scenario_count"] = 0

    return status


# --- MCP tool registration (thin wrappers) ---


@mcp.tool()
def parse_gwt(content: str | None = None, file_path: str | None = None) -> dict:
    """Parse GWT specs from a string or .gwt file into structured scenarios.

    Provide either `content` (raw GWT text) or `file_path` (path to a .gwt file).
    Returns parsed scenarios with clauses, source locations, and any parse errors.
    """
    return _parse_gwt(content, file_path)


@mcp.tool()
def build_state_graph(content: str | None = None, file_path: str | None = None) -> dict:
    """Build a state machine graph from GWT specs.

    Extracts states (from GIVEN/THEN clauses) and transitions (from WHEN clauses).
    Identifies entry points, terminal states, and cycles.
    """
    return _build_state_graph(content, file_path)


@mcp.tool()
def analyze_spec_gaps(
    content: str | None = None,
    file_path: str | None = None,
    project_root: str | None = None,
) -> dict:
    """Analyze GWT specs for completeness gaps.

    Finds dead ends, unreachable states, contradictions, missing error paths,
    and missing negative scenarios. Respects previously triaged gaps.
    """
    return _analyze_spec_gaps(content, file_path, project_root)


@mcp.tool()
def check_guardian(
    content: str | None = None,
    file_path: str | None = None,
    sensitivity: str = "medium",
    allowlist: list[str] | None = None,
) -> dict:
    """Check GWT specs for implementation detail leakage using regex patterns.

    Detects class names, database terms, API routes, and framework references
    that don't belong in behavioral specifications.
    """
    return _check_guardian(content, file_path, sensitivity, allowlist)


@mcp.tool()
def find_equivalences(
    content: str | None = None,
    file_path: str | None = None,
    threshold: float = 0.7,
) -> dict:
    """Find semantically equivalent state labels that may be duplicates.

    Uses string similarity matching to detect state labels that could
    be merged or standardized.
    """
    return _find_equivalences(content, file_path, threshold)


@mcp.tool()
def export_graph(
    content: str | None = None,
    file_path: str | None = None,
    format: str = "json",
) -> dict:
    """Export the state machine graph as DOT (Graphviz) or JSON.

    Args:
        format: "dot" for Graphviz DOT format, "json" for JSON (default).
    """
    return _export_graph(content, file_path, format)


@mcp.tool()
def detect_project(project_root: str = ".") -> dict:
    """Detect the programming language and test framework of a project.

    Scans file extensions, marker files (pyproject.toml, package.json, etc.),
    and framework config files to determine the project's tech stack.
    """
    return _detect_project(project_root)


@mcp.tool()
def get_project_status(project_root: str = ".") -> dict:
    """Get the current spec-eng project status.

    Returns spec count, scenario count, graph size, gap count,
    pipeline state, and initialization status.
    """
    return _get_project_status(project_root)
