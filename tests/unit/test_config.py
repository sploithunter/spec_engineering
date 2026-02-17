"""Unit tests for spec_eng.config."""

import json
from pathlib import Path

import pytest

from spec_eng.config import (
    detect_framework,
    detect_language,
    ensure_initialized,
    is_initialized,
    load_config,
    save_config,
)
from spec_eng.models import ProjectConfig


class TestSaveLoadConfig:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        config = ProjectConfig(language="python", framework="pytest")
        path = save_config(config, tmp_path)
        assert path.exists()

    def test_save_creates_spec_eng_dir(self, tmp_path: Path) -> None:
        config = ProjectConfig()
        save_config(config, tmp_path)
        assert (tmp_path / ".spec-eng").is_dir()

    def test_roundtrip(self, tmp_path: Path) -> None:
        config = ProjectConfig(
            language="python",
            framework="pytest",
            vocabulary=["player", "board"],
            auto_analysis=True,
        )
        save_config(config, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded.language == "python"
        assert loaded.framework == "pytest"
        assert loaded.vocabulary == ["player", "board"]
        assert loaded.auto_analysis is True

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path)

    def test_save_is_valid_json(self, tmp_path: Path) -> None:
        config = ProjectConfig(language="rust")
        path = save_config(config, tmp_path)
        data = json.loads(path.read_text())
        assert data["language"] == "rust"

    def test_guardian_roundtrip(self, tmp_path: Path) -> None:
        config = ProjectConfig()
        config.guardian = {
            "enabled": True,
            "sensitivity": "low",
            "allowlist": ["API key"],
        }
        save_config(config, tmp_path)
        loaded = load_config(tmp_path)
        assert loaded.guardian["sensitivity"] == "low"
        assert "API key" in loaded.guardian["allowlist"]


class TestDetectLanguage:
    def test_detect_python_from_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        langs = detect_language(tmp_path)
        assert "python" in langs

    def test_detect_python_from_file(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("print('hello')")
        langs = detect_language(tmp_path)
        assert "python" in langs

    def test_detect_multiple(self, tmp_path: Path) -> None:
        (tmp_path / "main.ts").write_text("console.log('hi')")
        (tmp_path / "lib.rs").write_text("fn main() {}")
        langs = detect_language(tmp_path)
        assert "typescript" in langs
        assert "rust" in langs

    def test_empty_project(self, tmp_path: Path) -> None:
        langs = detect_language(tmp_path)
        assert langs == []

    def test_skips_hidden_dirs(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".venv"
        hidden.mkdir()
        (hidden / "test.py").write_text("x = 1")
        langs = detect_language(tmp_path)
        assert "python" not in langs


class TestDetectFramework:
    def test_python_pytest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\n')
        assert detect_framework(tmp_path, "python") == "pytest"

    def test_python_default(self, tmp_path: Path) -> None:
        assert detect_framework(tmp_path, "python") == "unittest"

    def test_typescript_jest(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"devDependencies":{"jest":"^29"}}')
        assert detect_framework(tmp_path, "typescript") == "jest"

    def test_rust(self, tmp_path: Path) -> None:
        assert detect_framework(tmp_path, "rust") == "cargo-test"


class TestIsInitialized:
    def test_not_initialized(self, tmp_path: Path) -> None:
        assert not is_initialized(tmp_path)

    def test_initialized(self, initialized_project: Path) -> None:
        assert is_initialized(initialized_project)


class TestEnsureInitialized:
    def test_raises_when_not_initialized(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="not initialized"):
            ensure_initialized(tmp_path)

    def test_returns_config(self, initialized_project: Path) -> None:
        config = ensure_initialized(initialized_project)
        assert config.language == "python"
