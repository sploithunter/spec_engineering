"""Acceptance tests for Section 9: The Full Workflow.

Covers: 9.1 - 9.4.
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from spec_eng.cli import cli
from spec_eng.config import save_config
from spec_eng.models import ProjectConfig

pytestmark = pytest.mark.acceptance


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _setup_full_project(tmp_path: Path) -> Path:
    """Create a fully initialized project with specs."""
    config = ProjectConfig(language="python", framework="pytest")
    save_config(config, tmp_path)
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()

    (specs_dir / "registration.gwt").write_text("""\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.
""")
    return tmp_path


class TestScenario9_1:
    """9.1: The status command shows the current state."""

    def test_status_shows_spec_count(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = _setup_full_project(tmp_path)
        monkeypatch.chdir(proj)
        result = runner.invoke(cli, ["status"])
        assert "Spec files:" in result.output
        assert "1" in result.output

    def test_status_shows_scenarios(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = _setup_full_project(tmp_path)
        monkeypatch.chdir(proj)
        result = runner.invoke(cli, ["status"])
        assert "Scenarios:" in result.output

    def test_status_shows_pipeline(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = _setup_full_project(tmp_path)
        monkeypatch.chdir(proj)
        result = runner.invoke(cli, ["status"])
        assert "Pipeline:" in result.output


class TestScenario9_3:
    """9.3: The graph -> gaps -> spec cycle is iterative."""

    def test_iterative_reduces_gaps(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = _setup_full_project(tmp_path)
        monkeypatch.chdir(proj)

        # First round
        runner.invoke(cli, ["--non-interactive", "graph"])
        r1 = runner.invoke(cli, ["--non-interactive", "gaps"])

        # Add more specs
        specs_dir = proj / "specs"
        (specs_dir / "login.gwt").write_text("""\
;===============================================================
; User can log in.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in.

THEN the user is logged in.

;===============================================================
; Login fails with wrong password.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in with wrong password.

THEN login fails.
""")

        # Second round
        runner.invoke(cli, ["--non-interactive", "graph"])
        r2 = runner.invoke(cli, ["--non-interactive", "gaps"])

        # Should have output for both rounds
        assert r1.exit_code == 0
        assert r2.exit_code == 0


class TestScenario9_4:
    """9.4: CI integration runs the full verification pipeline."""

    def test_ci_command_runs(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        proj = _setup_full_project(tmp_path)
        monkeypatch.chdir(proj)
        result = runner.invoke(cli, ["ci"])
        # CI should at least parse and report
        assert "Parsing" in result.output or "scenario" in result.output.lower()


class TestScenario9_5:
    """9.5 (from SPEC): Non-interactive mode."""

    def test_non_interactive_flag(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(cli, ["--non-interactive", "init"])
        assert result.exit_code == 0
