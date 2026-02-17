"""E2E test: Full workflow from init to test.

Fourth E2E checkpoint: init -> write specs -> graph -> gaps -> bootstrap -> generate.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from spec_eng.cli import cli
from spec_eng.config import save_config
from spec_eng.models import ProjectConfig

pytestmark = pytest.mark.e2e


class TestFullWorkflow:
    def test_init_to_generate(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full workflow: init -> new -> graph -> gaps -> bootstrap -> generate."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        # Create a Python project marker
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

        # Step 1: init
        result = runner.invoke(cli, ["--non-interactive", "init"])
        assert result.exit_code == 0

        # Step 2: Create specs manually (simulating new + edit)
        specs_dir = tmp_path / "specs"
        (specs_dir / "registration.gwt").write_text("""\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.

;===============================================================
; User can log in after registration.
;===============================================================
GIVEN there is 1 registered user.

WHEN the user logs in.

THEN the user is logged in.

;===============================================================
; Registration fails with taken email.
;===============================================================
GIVEN there is 1 registered user.

WHEN another user registers with the same email.

THEN registration fails.
""")

        # Step 3: graph
        result = runner.invoke(cli, ["graph"])
        assert result.exit_code == 0
        assert "states" in result.output.lower()

        # Step 4: gaps
        result = runner.invoke(cli, ["--non-interactive", "gaps"])
        assert result.exit_code == 0

        # Step 5: bootstrap
        result = runner.invoke(cli, ["bootstrap"])
        assert result.exit_code == 0
        assert "bootstrapped" in result.output.lower()

        # Step 6: parse
        result = runner.invoke(cli, ["parse"])
        assert result.exit_code == 0
        assert "3 scenario(s)" in result.output

        # Step 7: generate
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code == 0
        assert "test_registration.py" in result.output

        # Verify generated file exists
        assert (tmp_path / ".spec-eng" / "generated" / "test_registration.py").exists()

        # Step 8: status
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Spec files: 1" in result.output
        assert "Scenarios: 3" in result.output
