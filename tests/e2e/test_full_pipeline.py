"""E2E test: Parse -> Generate -> Validate pipeline.

Third E2E checkpoint.
"""

from pathlib import Path

import pytest

from spec_eng.config import save_config
from spec_eng.generator import generate_ir, generate_tests
from spec_eng.models import ProjectConfig
from spec_eng.parser import parse_gwt_file, parse_gwt_string
from spec_eng.pipeline import bootstrap_pipeline

pytestmark = pytest.mark.e2e


class TestFullPipeline:
    def test_parse_generate_validate(self, tmp_path: Path) -> None:
        """Parse GWT -> Generate tests -> Validate generated code."""
        # Setup project
        config = ProjectConfig(language="python", framework="pytest")
        save_config(config, tmp_path)
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()

        # Write specs
        (specs_dir / "registration.gwt").write_text("""\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.

;===============================================================
; User can log in.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in.

THEN the user is logged in.
""")

        # Bootstrap
        summary = bootstrap_pipeline(tmp_path)
        assert summary["validation"] == "passed"

        # Parse
        result = parse_gwt_file(specs_dir / "registration.gwt")
        assert len(result.scenarios) == 2

        # Generate IR
        ir = generate_ir(result)
        assert len(ir) == 2
        assert ir[0]["title"] == "User can register."

        # Generate tests
        generated = generate_tests(tmp_path, result)
        assert "test_registration.py" in generated

        # Validate generated code compiles
        for code in generated.values():
            compile(code, "<generated>", "exec")

        # Verify generated file exists on disk
        gen_dir = tmp_path / ".spec-eng" / "generated"
        assert (gen_dir / "test_registration.py").exists()
