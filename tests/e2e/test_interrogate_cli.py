"""E2E tests for interrogation CLI command."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from spec_eng.cli import cli

pytestmark = pytest.mark.e2e


def test_interrogate_creates_session_and_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Initialize minimal project config
    (tmp_path / ".spec-eng").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / ".spec-eng" / "config.json").write_text(
        '{"version":"0.1.0","language":"python","framework":"pytest"}'
    )

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copy(repo_root / "specs" / "vocab.yaml", tmp_path / "specs" / "vocab.yaml")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(cli, ["interrogate", "--idea", "User registration"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / "specs" / "user-registration.txt").exists()
    assert (tmp_path / "specs" / "user-registration.dal").exists()
    assert (tmp_path / ".spec-eng" / "interrogation" / "user-registration.json").exists()
    assert "Open questions:" in result.output


def test_interrogate_approval_requires_stable_resolved_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".spec-eng").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / ".spec-eng" / "config.json").write_text(
        '{"version":"0.1.0","language":"python","framework":"pytest"}'
    )

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copy(repo_root / "specs" / "vocab.yaml", tmp_path / "specs" / "vocab.yaml")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    # first iteration creates session
    runner.invoke(cli, ["interrogate", "--idea", "Checkout Flow"])

    # approval should fail when questions unresolved
    fail = runner.invoke(
        cli,
        ["interrogate", "--idea", "Checkout Flow", "--approve"],
    )
    assert fail.exit_code != 0
    assert "unresolved blocking questions" in fail.output

    # answer blocking questions and run two cycles for stability
    args = [
        "interrogate",
        "--idea",
        "Checkout Flow",
        "--answer",
        "success_criteria=user can complete checkout",
        "--answer",
        "failure_case=declined card is rejected",
        "--answer",
        "constraints=checkout finishes within 2 minutes",
    ]
    r1 = runner.invoke(cli, args)
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli, args)
    assert r2.exit_code == 0, r2.output

    ok = runner.invoke(cli, args + ["--approve"])
    assert ok.exit_code == 0, ok.output
    assert "Approved: yes" in ok.output


def test_interrogate_then_generate_consumes_ir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".spec-eng").mkdir()
    (tmp_path / "specs").mkdir()
    (tmp_path / ".spec-eng" / "config.json").write_text(
        '{"version":"0.1.0","language":"python","framework":"pytest"}'
    )

    repo_root = Path(__file__).resolve().parents[2]
    shutil.copy(repo_root / "specs" / "vocab.yaml", tmp_path / "specs" / "vocab.yaml")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    args = [
        "interrogate",
        "--idea",
        "Password Reset",
        "--answer",
        "success_criteria=user can reset password by email link",
        "--answer",
        "failure_case=invalid token is rejected",
        "--answer",
        "constraints=reset link expires after 15 minutes",
    ]

    first = runner.invoke(cli, args)
    second = runner.invoke(cli, args)
    approved = runner.invoke(cli, args + ["--approve"])
    generated = runner.invoke(cli, ["generate"])

    assert first.exit_code == 0, first.output
    assert second.exit_code == 0, second.output
    assert approved.exit_code == 0, approved.output
    assert generated.exit_code == 0, generated.output
    assert "from IR" in generated.output
    assert (tmp_path / ".spec-eng" / "generated" / "test_password-reset.py").exists()
