"""Unit tests for spec_eng.pipeline."""

import json
from pathlib import Path

import pytest

from spec_eng.config import save_config
from spec_eng.models import ProjectConfig
from spec_eng.pipeline import bootstrap_pipeline, is_bootstrapped


@pytest.fixture
def py_project(tmp_path: Path) -> Path:
    """Create a minimal initialized Python project."""
    config = ProjectConfig(language="python", framework="pytest")
    save_config(config, tmp_path)
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    (specs_dir / "test.gwt").write_text(
        ";===\n; Test.\n;===\nGIVEN a.\n\nWHEN b.\n\nTHEN c.\n"
    )
    return tmp_path


class TestBootstrapPipeline:
    def test_creates_pipeline_dir(self, py_project: Path) -> None:
        bootstrap_pipeline(py_project)
        assert (py_project / ".spec-eng" / "pipeline").is_dir()

    def test_creates_config(self, py_project: Path) -> None:
        bootstrap_pipeline(py_project)
        config_path = py_project / ".spec-eng" / "pipeline" / "config.json"
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        assert data["language"] == "python"

    def test_summary(self, py_project: Path) -> None:
        summary = bootstrap_pipeline(py_project)
        assert summary["language"] == "python"
        assert summary["framework"] == "pytest"

    def test_validation_passes(self, py_project: Path) -> None:
        summary = bootstrap_pipeline(py_project)
        assert summary["validation"] == "passed"

    def test_refresh(self, py_project: Path) -> None:
        bootstrap_pipeline(py_project)
        summary = bootstrap_pipeline(py_project, refresh=True)
        assert summary["validation"] == "passed"


class TestIsBootstrapped:
    def test_not_bootstrapped(self, tmp_path: Path) -> None:
        assert not is_bootstrapped(tmp_path)

    def test_bootstrapped(self, py_project: Path) -> None:
        bootstrap_pipeline(py_project)
        assert is_bootstrapped(py_project)
