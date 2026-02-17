"""Test execution and result reporting."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestResult:
    """Result of running a test suite."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    output: str = ""
    failing_tests: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors


def run_acceptance_tests(project_root: Path) -> TestResult:
    """Run generated acceptance tests.

    Regenerates tests if specs have changed since last generation.
    """
    generated_dir = project_root / ".spec-eng" / "generated"

    if not generated_dir.exists() or not list(generated_dir.glob("test_*.py")):
        return TestResult(output="No generated tests found. Run `spec-eng generate` first.")

    # Check if specs are newer than generated tests
    specs_dir = project_root / "specs"
    if specs_dir.exists():
        _regenerate_if_stale(project_root, specs_dir, generated_dir)

    return _run_pytest(generated_dir)


def run_unit_tests(project_root: Path) -> TestResult:
    """Run the project's unit tests."""
    # Look for common test directories
    test_dirs = [
        project_root / "tests",
        project_root / "test",
    ]

    test_dir = None
    for d in test_dirs:
        if d.is_dir():
            test_dir = d
            break

    if test_dir is None:
        return TestResult(output="No unit test directory found.")

    return _run_pytest(test_dir)


def run_verify(project_root: Path) -> TestResult:
    """Run both acceptance and unit tests.

    Both must pass for verification to succeed.
    """
    acceptance = run_acceptance_tests(project_root)
    unit = run_unit_tests(project_root)

    combined = TestResult(
        passed=acceptance.passed + unit.passed,
        failed=acceptance.failed + unit.failed,
        skipped=acceptance.skipped + unit.skipped,
        errors=acceptance.errors + unit.errors,
        failing_tests=acceptance.failing_tests + unit.failing_tests,
    )

    parts = []
    parts.append(f"Acceptance: {acceptance.passed} passed, {acceptance.failed} failed")
    parts.append(f"Unit: {unit.passed} passed, {unit.failed} failed")

    if not unit.total and acceptance.success:
        parts.append("Warning: Only one test stream exists. Unit tests are needed.")

    combined.output = "\n".join(parts)
    return combined


def _run_pytest(test_path: Path) -> TestResult:
    """Run pytest on a directory and parse results."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_path), "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return TestResult(errors=1, output="Test execution timed out (5 minutes)")
    except FileNotFoundError:
        return TestResult(errors=1, output="pytest not found")

    output = proc.stdout + proc.stderr
    return _parse_pytest_output(output, proc.returncode)


def _parse_pytest_output(output: str, returncode: int) -> TestResult:
    """Parse pytest output to extract results."""
    result = TestResult(output=output)

    for line in output.split("\n"):
        line = line.strip()

        # Parse summary line like "5 passed, 2 failed, 1 skipped"
        if "passed" in line or "failed" in line or "error" in line:
            import re

            passed = re.search(r"(\d+) passed", line)
            failed = re.search(r"(\d+) failed", line)
            skipped = re.search(r"(\d+) skipped", line)
            errors = re.search(r"(\d+) error", line)

            if passed:
                result.passed = int(passed.group(1))
            if failed:
                result.failed = int(failed.group(1))
            if skipped:
                result.skipped = int(skipped.group(1))
            if errors:
                result.errors = int(errors.group(1))

        # Track failing test names
        if line.startswith("FAILED"):
            result.failing_tests.append(line)

    return result


def _regenerate_if_stale(
    project_root: Path, specs_dir: Path, generated_dir: Path
) -> None:
    """Regenerate tests if any spec file is newer than its generated test."""
    from spec_eng.generator import generate_tests
    from spec_eng.models import ParseResult
    from spec_eng.parser import parse_gwt_file

    needs_regen = False
    for gwt_file in specs_dir.glob("*.gwt"):
        test_file = generated_dir / f"test_{gwt_file.stem}.py"
        if not test_file.exists():
            needs_regen = True
            break
        if gwt_file.stat().st_mtime > test_file.stat().st_mtime:
            needs_regen = True
            break

    if needs_regen:
        all_scenarios = []
        for gwt_file in sorted(specs_dir.glob("*.gwt")):
            r = parse_gwt_file(gwt_file)
            all_scenarios.extend(r.scenarios)
        if all_scenarios:
            generate_tests(project_root, ParseResult(scenarios=all_scenarios))
