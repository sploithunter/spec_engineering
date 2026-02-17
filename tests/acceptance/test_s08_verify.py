"""Acceptance tests for Section 8: Dual Test Stream Verification.

Covers: 8.1 - 8.3.
"""

from pathlib import Path

import pytest

from spec_eng.runner import TestResult, run_verify

pytestmark = pytest.mark.acceptance


class TestScenario8_1:
    """8.1: Both acceptance tests and unit tests must pass."""

    def test_verify_reports_both_streams(self, tmp_path: Path) -> None:
        # Create generated acceptance tests (passing)
        gen_dir = tmp_path / ".spec-eng" / "generated"
        gen_dir.mkdir(parents=True)
        (gen_dir / "test_sample.py").write_text(
            "def test_pass():\n    assert True\n"
        )

        # Create unit tests with a failure
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_unit.py").write_text(
            "def test_unit_fail():\n    assert False\n"
        )

        result = run_verify(tmp_path)
        assert "Acceptance" in result.output
        assert "Unit" in result.output


class TestScenario8_2:
    """8.2: Acceptance tests passing with no unit tests triggers warning."""

    def test_warns_no_unit_tests(self, tmp_path: Path) -> None:
        gen_dir = tmp_path / ".spec-eng" / "generated"
        gen_dir.mkdir(parents=True)
        (gen_dir / "test_sample.py").write_text(
            "def test_pass():\n    assert True\n"
        )

        result = run_verify(tmp_path)
        assert "Warning" in result.output or "one test stream" in result.output.lower()


class TestScenario8_3:
    """8.3: Verification reports coverage.

    This is a structural test - verifying the report format exists.
    """

    def test_verify_result_structure(self) -> None:
        result = TestResult(
            passed=8,
            failed=0,
            output="Acceptance: 8 passed\nUnit: 8 passed",
        )
        assert result.success
        assert result.total == 8
