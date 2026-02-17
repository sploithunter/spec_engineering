"""Unit tests for spec_eng.runner."""

from pathlib import Path
from unittest.mock import patch

import pytest

from spec_eng.runner import TestResult, _parse_pytest_output, run_acceptance_tests, run_verify


class TestTestResult:
    def test_success(self) -> None:
        r = TestResult(passed=5)
        assert r.success

    def test_failure(self) -> None:
        r = TestResult(passed=3, failed=2)
        assert not r.success

    def test_total(self) -> None:
        r = TestResult(passed=3, failed=2, skipped=1)
        assert r.total == 6


class TestParsePytestOutput:
    def test_parse_success(self) -> None:
        output = "5 passed in 0.5s"
        result = _parse_pytest_output(output, 0)
        assert result.passed == 5
        assert result.success

    def test_parse_failures(self) -> None:
        output = "3 passed, 2 failed in 1.2s"
        result = _parse_pytest_output(output, 1)
        assert result.passed == 3
        assert result.failed == 2
        assert not result.success

    def test_parse_skipped(self) -> None:
        output = "3 passed, 1 skipped in 0.3s"
        result = _parse_pytest_output(output, 0)
        assert result.skipped == 1

    def test_parse_errors(self) -> None:
        output = "1 error in 0.1s"
        result = _parse_pytest_output(output, 1)
        assert result.errors == 1

    def test_parse_failing_test_names(self) -> None:
        output = "FAILED tests/test_foo.py::test_bar - AssertionError\n1 failed"
        result = _parse_pytest_output(output, 1)
        assert len(result.failing_tests) == 1


class TestRunAcceptanceTests:
    def test_no_generated_dir(self, tmp_path: Path) -> None:
        result = run_acceptance_tests(tmp_path)
        assert "No generated tests" in result.output

    def test_empty_generated_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".spec-eng" / "generated").mkdir(parents=True)
        result = run_acceptance_tests(tmp_path)
        assert "No generated tests" in result.output


class TestRunVerify:
    def test_warns_no_unit_tests(self, tmp_path: Path) -> None:
        # Create generated tests
        gen_dir = tmp_path / ".spec-eng" / "generated"
        gen_dir.mkdir(parents=True)
        (gen_dir / "test_sample.py").write_text(
            "def test_sample():\n    pass\n"
        )
        result = run_verify(tmp_path)
        assert "Unit" in result.output or "unit" in result.output.lower()
