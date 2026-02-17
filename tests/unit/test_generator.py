"""Unit tests for spec_eng.generator."""

from pathlib import Path

import pytest

from spec_eng.generator import PytestGenerator, generate_ir, generate_tests
from spec_eng.models import Clause, ParseResult, Scenario


def _make_scenario(title: str, given: str, when: str, then: str, source: str = "test.gwt") -> Scenario:
    return Scenario(
        title=title,
        givens=[Clause("GIVEN", given, 1)],
        whens=[Clause("WHEN", when, 3)],
        thens=[Clause("THEN", then, 5)],
        source_file=source,
        line_number=1,
    )


class TestPytestGenerator:
    def test_generates_valid_python(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("User registers", "no users", "register", "1 user")]
        code = gen.generate_test_file(scenarios, "registration")
        compile(code, "<test>", "exec")

    def test_test_function_name(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("User registers", "no users", "register", "1 user")]
        code = gen.generate_test_file(scenarios, "registration")
        assert "def test_user_registers" in code

    def test_given_comment(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("Test", "no users", "act", "result")]
        code = gen.generate_test_file(scenarios, "test")
        assert "# GIVEN no users." in code

    def test_when_comment(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("Test", "state", "do something", "result")]
        code = gen.generate_test_file(scenarios, "test")
        assert "# WHEN do something." in code

    def test_then_comment(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("Test", "state", "act", "expected outcome")]
        code = gen.generate_test_file(scenarios, "test")
        assert "# THEN expected outcome." in code

    def test_source_reference(self) -> None:
        gen = PytestGenerator()
        scenarios = [_make_scenario("Test", "a", "b", "c", source="specs/reg.gwt")]
        code = gen.generate_test_file(scenarios, "reg")
        assert "specs/reg.gwt" in code

    def test_multiple_scenarios(self) -> None:
        gen = PytestGenerator()
        scenarios = [
            _make_scenario("First", "a", "b", "c"),
            _make_scenario("Second", "d", "e", "f"),
        ]
        code = gen.generate_test_file(scenarios, "test")
        assert "def test_first" in code
        assert "def test_second" in code

    def test_do_not_edit_warning(self) -> None:
        gen = PytestGenerator()
        code = gen.generate_test_file([], "test")
        assert "DO NOT EDIT" in code


class TestGenerateIR:
    def test_ir_structure(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("Test", "precond", "action", "result"),
        ])
        ir = generate_ir(result)
        assert len(ir) == 1
        assert ir[0]["title"] == "Test"
        assert len(ir[0]["givens"]) == 1
        assert len(ir[0]["whens"]) == 1
        assert len(ir[0]["thens"]) == 1

    def test_ir_metadata(self) -> None:
        result = ParseResult(scenarios=[
            _make_scenario("Test", "a", "b", "c", source="file.gwt"),
        ])
        ir = generate_ir(result)
        assert ir[0]["source_file"] == "file.gwt"
        assert ir[0]["line_number"] == 1


class TestGenerateTests:
    def test_creates_files(self, tmp_path: Path) -> None:
        (tmp_path / ".spec-eng").mkdir()
        result = ParseResult(scenarios=[
            _make_scenario("Test", "a", "b", "c", source="specs/reg.gwt"),
        ])
        generated = generate_tests(tmp_path, result)
        assert len(generated) == 1
        assert (tmp_path / ".spec-eng" / "generated" / "test_reg.py").exists()

    def test_one_file_per_source(self, tmp_path: Path) -> None:
        (tmp_path / ".spec-eng").mkdir()
        result = ParseResult(scenarios=[
            _make_scenario("S1", "a", "b", "c", source="specs/auth.gwt"),
            _make_scenario("S2", "d", "e", "f", source="specs/profile.gwt"),
        ])
        generated = generate_tests(tmp_path, result)
        assert "test_auth.py" in generated
        assert "test_profile.py" in generated
