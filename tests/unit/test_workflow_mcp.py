"""Unit tests for standalone workflow MCP helper functions."""

from __future__ import annotations

import shutil
from pathlib import Path

from spec_eng.workflow_mcp import _interrogate, _spec_check, _spec_compile


def _setup_project(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    (tmp_path / "specs").mkdir(parents=True)
    shutil.copy(repo / "specs" / "vocab.yaml", tmp_path / "specs" / "vocab.yaml")
    shutil.copy(repo / "tests" / "fixtures" / "dual-spec-sample.txt", tmp_path / "specs" / "sample.txt")


def test_spec_compile_helper(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = _spec_compile("specs/sample.txt", project_root=str(tmp_path))
    assert result["ok"] is True
    assert "dal" in result["outputs"]
    assert (tmp_path / "specs" / "sample.dal").exists()


def test_spec_check_helper(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    leaky = tmp_path / "specs" / "leaky.txt"
    leaky.write_text("GIVEN the UserService uses a repository.\n")

    result = _spec_check("specs/leaky.txt", project_root=str(tmp_path))
    assert result["ok"] is False
    assert result["count"] > 0


def test_interrogate_helper(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = _interrogate(
        idea="Password Reset",
        project_root=str(tmp_path),
        answers=[
            "success_criteria=user can reset password",
            "failure_case=invalid token is rejected",
            "constraints=link expires in 15 minutes",
        ],
        approve=False,
    )
    assert result["ok"] is True
    assert result["session"]["iteration"] == 1
