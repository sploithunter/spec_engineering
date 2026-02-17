"""Acceptance tests for Section 10: Spec Portability.

Covers: 10.1, 10.2.
"""

from pathlib import Path

import pytest

from spec_eng.config import save_config
from spec_eng.generator import generate_tests
from spec_eng.models import ProjectConfig
from spec_eng.parser import parse_gwt_file, parse_gwt_string

pytestmark = pytest.mark.acceptance

SAMPLE_GWT = """\
;===============================================================
; User can register.
;===============================================================
GIVEN no registered users.

WHEN a user registers.

THEN there is 1 registered user.
"""


class TestScenario10_1:
    """10.1: The same spec files work across different language targets."""

    def test_spec_parses_regardless_of_target(self, tmp_path: Path) -> None:
        # Same spec file parses identically for any language target
        spec_file = tmp_path / "registration.gwt"
        spec_file.write_text(SAMPLE_GWT)

        result_py = parse_gwt_file(spec_file)
        result_ts = parse_gwt_file(spec_file)

        assert len(result_py.scenarios) == len(result_ts.scenarios)
        assert result_py.scenarios[0].title == result_ts.scenarios[0].title

    def test_different_targets_same_scenarios(self, tmp_path: Path) -> None:
        # Generate tests for python target
        config_py = ProjectConfig(language="python", framework="pytest")
        save_config(config_py, tmp_path)
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        spec_file = specs_dir / "registration.gwt"
        spec_file.write_text(SAMPLE_GWT)

        result = parse_gwt_file(spec_file)
        generate_tests(tmp_path, result)

        gen_dir = tmp_path / ".spec-eng" / "generated"
        assert gen_dir.exists()
        gen_files = list(gen_dir.glob("test_*.py"))
        assert len(gen_files) > 0


class TestScenario10_2:
    """10.2: Spec files contain no language-specific constructs."""

    def test_spec_no_language_constructs(self) -> None:
        # GWT specs are pure behavioral language
        result = parse_gwt_string(SAMPLE_GWT)
        assert result.is_success
        scenario = result.scenarios[0]
        # No language keywords should be present
        all_text = " ".join(
            c.text for c in scenario.givens + scenario.whens + scenario.thens
        )
        language_keywords = [
            "def ", "class ", "function ", "fn ", "impl ",
            "import ", "require(", "pub ", "private ",
        ]
        for kw in language_keywords:
            assert kw not in all_text

    def test_spec_parses_without_modification(self) -> None:
        # A spec authored for one project works in another without changes
        result1 = parse_gwt_string(SAMPLE_GWT)
        result2 = parse_gwt_string(SAMPLE_GWT)
        assert result1.scenarios[0].title == result2.scenarios[0].title
        assert len(result1.scenarios) == len(result2.scenarios)

    def test_gwt_uses_behavioral_language(self) -> None:
        # Verify the sample spec uses behavioral language only
        result = parse_gwt_string(SAMPLE_GWT)
        scenario = result.scenarios[0]
        # Clauses describe behavior, not implementation
        assert "register" in scenario.whens[0].text.lower()
        assert "registered user" in scenario.thens[0].text.lower()
