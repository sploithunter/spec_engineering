"""Acceptance tests for Section 6: Pipeline Bootstrap.

Covers: 6.1 - 6.6.
"""

import json
from pathlib import Path

import pytest

from spec_eng.config import save_config
from spec_eng.generator import PytestGenerator, generate_ir, generate_tests
from spec_eng.models import Clause, ParseResult, ProjectConfig, Scenario
from spec_eng.parser import parse_gwt_file
from spec_eng.pipeline import bootstrap_pipeline, is_bootstrapped

pytestmark = pytest.mark.acceptance


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    config = ProjectConfig(language="python", framework="pytest")
    save_config(config, tmp_path)
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    return tmp_path


def _write_spec(specs_dir: Path, name: str, content: str) -> Path:
    p = specs_dir / name
    p.write_text(content)
    return p


class TestScenario6_1:
    """6.1: A parser/generator pipeline is bootstrapped."""

    def test_parser_stored(self, py_project: Path) -> None:
        (py_project / "specs" / "test.gwt").write_text(
            ";===\n; Test.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        )
        bootstrap_pipeline(py_project)
        assert (py_project / ".spec-eng" / "pipeline").is_dir()

    def test_summary_shown(self, py_project: Path) -> None:
        (py_project / "specs" / "test.gwt").write_text(
            ";===\n; Test.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        )
        summary = bootstrap_pipeline(py_project)
        assert summary["language"] == "python"
        assert summary["framework"] == "pytest"


class TestScenario6_2:
    """6.2: The bootstrapped parser correctly parses all existing specs."""

    def test_all_files_parsed(self, py_project: Path) -> None:
        specs_dir = py_project / "specs"
        for i in range(5):
            _write_spec(specs_dir, f"spec{i}.gwt", (
                f";===\n; Scenario {i}.\n;===\n"
                f"GIVEN state {i}.\n\nWHEN event {i}.\n\nTHEN result {i}.\n"
            ))

        all_scenarios = []
        for gwt_file in sorted(specs_dir.glob("*.gwt")):
            r = parse_gwt_file(gwt_file)
            all_scenarios.extend(r.scenarios)

        assert len(all_scenarios) == 5

    def test_ir_has_source_refs(self, py_project: Path) -> None:
        specs_dir = py_project / "specs"
        _write_spec(specs_dir, "reg.gwt", (
            ";===\n; Test.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        ))
        r = parse_gwt_file(specs_dir / "reg.gwt")
        ir = generate_ir(r)
        assert ir[0]["source_file"] is not None


class TestScenario6_3:
    """6.3: The bootstrapped generator produces runnable tests."""

    def test_generated_tests_valid(self, py_project: Path) -> None:
        specs_dir = py_project / "specs"
        _write_spec(specs_dir, "auth.gwt", (
            ";===\n; Login.\n;===\nGIVEN a user.\n\nWHEN user logs in.\n\nTHEN logged in.\n"
        ))
        r = parse_gwt_file(specs_dir / "auth.gwt")
        generated = generate_tests(py_project, r)
        for code in generated.values():
            compile(code, "<test>", "exec")

    def test_each_file_corresponds(self, py_project: Path) -> None:
        specs_dir = py_project / "specs"
        _write_spec(specs_dir, "auth.gwt", (
            ";===\n; Login.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        ))
        r = parse_gwt_file(specs_dir / "auth.gwt")
        generated = generate_tests(py_project, r)
        assert "test_auth.py" in generated


class TestScenario6_4:
    """6.4: The pipeline can be re-bootstrapped."""

    def test_refresh(self, py_project: Path) -> None:
        (py_project / "specs" / "t.gwt").write_text(
            ";===\n; T.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        )
        bootstrap_pipeline(py_project)
        summary = bootstrap_pipeline(py_project, refresh=True)
        assert summary["validation"] == "passed"


class TestScenario6_5:
    """6.5: The pipeline validates itself against a reference spec."""

    def test_validation_passes(self, py_project: Path) -> None:
        (py_project / "specs" / "t.gwt").write_text(
            ";===\n; T.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
        )
        summary = bootstrap_pipeline(py_project)
        assert summary["validation"] == "passed"


class TestScenario6_6:
    """6.6: The IR is inspectable and human-readable."""

    def test_ir_readable(self, py_project: Path) -> None:
        specs_dir = py_project / "specs"
        _write_spec(specs_dir, "test.gwt", (
            ";===\n; My scenario.\n;===\nGIVEN precond.\n\nWHEN action.\n\nTHEN result.\n"
        ))
        r = parse_gwt_file(specs_dir / "test.gwt")
        ir = generate_ir(r)
        # Each scenario has readable fields
        entry = ir[0]
        assert entry["title"] == "My scenario."
        assert entry["givens"][0]["text"] == "precond"
        assert entry["whens"][0]["text"] == "action"
        assert entry["thens"][0]["text"] == "result"
        assert "source_file" in entry
        assert "line_number" in entry
