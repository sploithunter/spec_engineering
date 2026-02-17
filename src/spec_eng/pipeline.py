"""Pipeline bootstrap: analyze project and create pipeline config."""

from __future__ import annotations

import json
from pathlib import Path

from spec_eng.config import ensure_initialized
from spec_eng.models import ProjectConfig

REFERENCE_SPEC = """\
;===============================================================
; Reference spec validates the pipeline is working.
;===============================================================
GIVEN a valid precondition.

WHEN an action occurs.

THEN the expected result happens.
"""


def bootstrap_pipeline(project_root: Path, refresh: bool = False) -> dict[str, str]:
    """Bootstrap or refresh the parser/generator pipeline.

    Creates .spec-eng/pipeline/ with pipeline configuration.
    Returns a summary dict of what was created.
    """
    config = ensure_initialized(project_root)

    pipeline_dir = project_root / ".spec-eng" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # Save pipeline config
    pipeline_config = {
        "language": config.language,
        "framework": config.framework,
        "version": config.version,
        "parser": "gwt",
        "generator": f"{config.framework or 'pytest'}_generator",
    }
    (pipeline_dir / "config.json").write_text(
        json.dumps(pipeline_config, indent=2)
    )

    # Validate with reference spec
    validation = _validate_pipeline(project_root, config)

    return {
        "pipeline_dir": str(pipeline_dir),
        "language": config.language,
        "framework": config.framework,
        "validation": "passed" if validation else "failed",
    }


def is_bootstrapped(project_root: Path) -> bool:
    """Check if the pipeline is bootstrapped."""
    return (project_root / ".spec-eng" / "pipeline" / "config.json").exists()


def _validate_pipeline(project_root: Path, config: ProjectConfig) -> bool:
    """Validate the pipeline against a reference spec."""
    from spec_eng.parser import parse_gwt_string

    result = parse_gwt_string(REFERENCE_SPEC, source_file="<reference>")
    if not result.is_success or not result.scenarios:
        return False

    # Try generating a test from the reference
    from spec_eng.generator import PytestGenerator

    generator = PytestGenerator()
    try:
        code = generator.generate_test_file(result.scenarios, "reference")
        # Verify it's valid Python by compiling
        compile(code, "<reference-test>", "exec")
        return True
    except Exception:
        return False
