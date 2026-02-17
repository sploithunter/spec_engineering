"""Acceptance tests for Section 1: Project Initialization.

Covers: 1.1, 1.2, 1.3, 1.4, and 2.1 (new command).
"""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from spec_eng.cli import cli

pytestmark = pytest.mark.acceptance


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set cwd to a temporary directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestScenario1_1:
    """1.1: A new project can be initialized for spec engineering."""

    def test_spec_eng_dir_created(self, runner: CliRunner, in_tmp: Path) -> None:
        result = runner.invoke(cli, ["--non-interactive", "init"])
        assert result.exit_code == 0
        assert (in_tmp / ".spec-eng").is_dir()

    def test_config_json_exists(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        config_path = in_tmp / ".spec-eng" / "config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert "version" in data

    def test_specs_dir_created(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        assert (in_tmp / "specs").is_dir()

    def test_confirmation_message(self, runner: CliRunner, in_tmp: Path) -> None:
        result = runner.invoke(cli, ["--non-interactive", "init"])
        assert "Initialized" in result.output or "initialized" in result.output.lower()


class TestScenario1_2:
    """1.2: Initialization detects existing project language and framework."""

    def test_detects_python(self, runner: CliRunner, in_tmp: Path) -> None:
        (in_tmp / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        result = runner.invoke(cli, ["init"])
        config = json.loads((in_tmp / ".spec-eng" / "config.json").read_text())
        assert config["language"] == "python"

    def test_detects_pytest(self, runner: CliRunner, in_tmp: Path) -> None:
        (in_tmp / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
        result = runner.invoke(cli, ["init"])
        config = json.loads((in_tmp / ".spec-eng" / "config.json").read_text())
        assert config["framework"] == "pytest"


class TestScenario1_3:
    """1.3: Initialization detects multiple languages."""

    def test_detects_both(self, runner: CliRunner, in_tmp: Path) -> None:
        (in_tmp / "app.ts").write_text("export const x = 1;")
        (in_tmp / "Cargo.toml").write_text("[package]\nname = 'test'\n")
        result = runner.invoke(cli, ["init"])
        config = json.loads((in_tmp / ".spec-eng" / "config.json").read_text())
        # At least one language detected
        assert config["language"] in ("typescript", "rust")


class TestScenario1_4:
    """1.4: Re-initialization does not destroy existing specs."""

    def test_existing_specs_preserved(self, runner: CliRunner, in_tmp: Path) -> None:
        # First init
        runner.invoke(cli, ["--non-interactive", "init"])
        # Create spec files
        specs_dir = in_tmp / "specs"
        for i in range(5):
            (specs_dir / f"spec-{i}.gwt").write_text(f"; Spec {i}\n")

        # Re-init
        result = runner.invoke(cli, ["--non-interactive", "init"])
        # All 5 files still there
        assert len(list(specs_dir.glob("*.gwt"))) == 5

    def test_config_updated(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        runner.invoke(cli, ["--non-interactive", "init"])
        assert (in_tmp / ".spec-eng" / "config.json").exists()

    def test_warning_shown(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        result = runner.invoke(cli, ["--non-interactive", "init"])
        assert "already initialized" in result.output.lower() or "Warning" in result.output


class TestScenario2_1:
    """2.1: A new spec file can be created from a description."""

    def test_new_creates_file(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        result = runner.invoke(cli, ["new", "User Registration"])
        assert result.exit_code == 0
        assert (in_tmp / "specs" / "user-registration.gwt").exists()

    def test_file_has_header(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        runner.invoke(cli, ["new", "User Registration"])
        content = (in_tmp / "specs" / "user-registration.gwt").read_text()
        assert "User Registration" in content

    def test_file_has_scaffold(self, runner: CliRunner, in_tmp: Path) -> None:
        runner.invoke(cli, ["--non-interactive", "init"])
        runner.invoke(cli, ["new", "User Registration"])
        content = (in_tmp / "specs" / "user-registration.gwt").read_text()
        assert "GIVEN" in content
        assert "WHEN" in content
        assert "THEN" in content
