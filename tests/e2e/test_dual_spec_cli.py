"""E2E tests for spec-compile and spec-check CLI commands."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from spec_eng.cli import cli

pytestmark = pytest.mark.e2e


def test_spec_compile_command_writes_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True)

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copy(repo_root / "specs" / "vocab.yaml", specs_dir / "vocab.yaml")
    shutil.copy(repo_root / "tests" / "fixtures" / "dual-spec-sample.txt", specs_dir / "fixture.txt")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["spec-compile", "--in", "specs/fixture.txt"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "specs" / "fixture.dal").exists()
    assert (tmp_path / "specs" / "fixture.txt.canonical").exists()
    assert (tmp_path / "acceptance-pipeline" / "ir" / "fixture.json").exists()
    assert (tmp_path / "acceptance-pipeline" / "roundtrip" / "fixture.diff.txt").exists()


def test_spec_check_command_reports_violations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True)

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copy(repo_root / "specs" / "vocab.yaml", specs_dir / "vocab.yaml")
    (specs_dir / "leaky.txt").write_text(
        "GIVEN the UserService has an empty userRepository.\n"
        "WHEN a POST request is sent to /api/users with JSON body.\n"
    )

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["spec-check", "--in", "specs/leaky.txt"])

    assert result.exit_code != 0
    assert "UserService" in result.output
    assert "Suggestion:" in result.output
