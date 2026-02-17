"""Configuration management for spec-eng projects."""

from __future__ import annotations

import json
from pathlib import Path

from spec_eng.models import ProjectConfig

SPEC_ENG_DIR = ".spec-eng"
CONFIG_FILE = "config.json"
SPECS_DIR = "specs"


def _config_path(project_root: Path) -> Path:
    return project_root / SPEC_ENG_DIR / CONFIG_FILE


def save_config(config: ProjectConfig, project_root: Path) -> Path:
    """Save project config to .spec-eng/config.json. Returns the config path."""
    spec_eng_dir = project_root / SPEC_ENG_DIR
    spec_eng_dir.mkdir(parents=True, exist_ok=True)
    path = _config_path(project_root)
    data = {
        "version": config.version,
        "language": config.language,
        "framework": config.framework,
        "guardian": config.guardian,
        "vocabulary": config.vocabulary,
        "auto_analysis": config.auto_analysis,
        "targets": config.targets,
    }
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")
    return path


def load_config(project_root: Path) -> ProjectConfig:
    """Load project config from .spec-eng/config.json."""
    path = _config_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"No config found at {path}")
    data = json.loads(path.read_text())
    return ProjectConfig(
        version=data.get("version", "0.1.0"),
        language=data.get("language", ""),
        framework=data.get("framework", ""),
        guardian=data.get("guardian", {"enabled": True, "sensitivity": "medium", "allowlist": []}),
        vocabulary=data.get("vocabulary", []),
        auto_analysis=data.get("auto_analysis", False),
        targets=data.get("targets", {}),
    )


def detect_language(project_root: Path) -> list[str]:
    """Detect programming languages in the project directory."""
    languages: list[str] = []
    extensions: dict[str, str] = {
        ".py": "python",
        ".ts": "typescript",
        ".js": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".clj": "clojure",
    }
    found: set[str] = set()
    for path in project_root.rglob("*"):
        if path.is_file() and path.suffix in extensions:
            # Skip hidden dirs and common vendor dirs
            parts = path.relative_to(project_root).parts
            if any(p.startswith(".") or p in ("node_modules", "venv", ".venv") for p in parts):
                continue
            found.add(extensions[path.suffix])

    # Also check for marker files
    if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists():
        found.add("python")
    if (project_root / "package.json").exists():
        # Check for TypeScript
        if (project_root / "tsconfig.json").exists():
            found.add("typescript")
        else:
            found.add("javascript")
    if (project_root / "Cargo.toml").exists():
        found.add("rust")
    if (project_root / "go.mod").exists():
        found.add("go")

    # Deterministic ordering
    priority = ["python", "typescript", "javascript", "rust", "go", "java", "ruby", "clojure"]
    for lang in priority:
        if lang in found:
            languages.append(lang)
    for lang in sorted(found):
        if lang not in languages:
            languages.append(lang)

    return languages


def detect_framework(project_root: Path, language: str) -> str:
    """Detect test framework for the given language."""
    if language == "python":
        # Check for pytest
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            if "pytest" in content:
                return "pytest"
        if (project_root / "pytest.ini").exists():
            return "pytest"
        if (project_root / "conftest.py").exists():
            return "pytest"
        if (project_root / "tests").is_dir():
            return "pytest"  # Default for Python
        return "unittest"

    if language == "typescript" or language == "javascript":
        pkg = project_root / "package.json"
        if pkg.exists():
            content = pkg.read_text()
            if "jest" in content:
                return "jest"
            if "vitest" in content:
                return "vitest"
            if "mocha" in content:
                return "mocha"
        return "jest"

    if language == "rust":
        return "cargo-test"

    if language == "go":
        return "go-test"

    if language == "java":
        pom = project_root / "pom.xml"
        if pom.exists():
            content = pom.read_text()
            if "junit" in content.lower():
                return "junit"
        return "junit"

    return ""


def is_initialized(project_root: Path) -> bool:
    """Check if the project is initialized for spec-eng."""
    return _config_path(project_root).exists()


def ensure_initialized(project_root: Path) -> ProjectConfig:
    """Ensure the project is initialized. Raises if not."""
    if not is_initialized(project_root):
        raise RuntimeError(
            "Project is not initialized. Run `spec-eng init` first."
        )
    return load_config(project_root)
