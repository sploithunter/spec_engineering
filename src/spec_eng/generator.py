"""Test code generation from GWT IR."""

from __future__ import annotations

import re
from pathlib import Path

from spec_eng.models import ParseResult, Scenario


class PytestGenerator:
    """Generates pytest test files from GWT scenarios."""

    def generate_test_file(
        self, scenarios: list[Scenario], module_name: str
    ) -> str:
        """Generate a complete pytest test file from scenarios."""
        lines = [
            f'"""Generated acceptance tests from {module_name}.gwt.',
            '',
            'DO NOT EDIT - this file is regenerated from GWT specs.',
            '"""',
            '',
            'import pytest',
            '',
            '',
        ]

        for i, scenario in enumerate(scenarios):
            func_name = self._make_test_name(scenario.title, i)
            lines.append(f'def {func_name}():')
            lines.append(f'    """Scenario: {scenario.title}"""')

            # Source reference
            if scenario.source_file:
                lines.append(
                    f'    # Source: {scenario.source_file}:'
                    f'{scenario.line_number}'
                )
            lines.append('')

            # GIVEN
            for g in scenario.givens:
                lines.append(f'    # GIVEN {g.text}.')
            lines.append('    # TODO: Set up preconditions')
            lines.append('')

            # WHEN
            for w in scenario.whens:
                lines.append(f'    # WHEN {w.text}.')
            lines.append('    # TODO: Perform action')
            lines.append('')

            # THEN
            for t in scenario.thens:
                lines.append(f'    # THEN {t.text}.')
            lines.append('    # TODO: Assert expected outcomes')
            lines.append('    pytest.skip("Not yet implemented")')
            lines.append('')
            lines.append('')

        return '\n'.join(lines)

    def _make_test_name(self, title: str, index: int) -> str:
        """Convert a scenario title to a valid Python test function name."""
        if not title:
            return f'test_scenario_{index}'
        # Remove punctuation and normalize
        name = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
        name = re.sub(r'\s+', '_', name.strip())
        if not name:
            return f'test_scenario_{index}'
        return f'test_{name}'


def generate_ir(parse_result: ParseResult) -> list[dict]:
    """Generate JSON IR from parsed scenarios."""
    ir: list[dict] = []
    for s in parse_result.scenarios:
        ir.append({
            "title": s.title,
            "source_file": s.source_file,
            "line_number": s.line_number,
            "givens": [{"text": g.text, "line": g.line_number} for g in s.givens],
            "whens": [{"text": w.text, "line": w.line_number} for w in s.whens],
            "thens": [{"text": t.text, "line": t.line_number} for t in s.thens],
        })
    return ir


def generate_tests(
    project_root: Path, parse_result: ParseResult
) -> dict[str, str]:
    """Generate test files from parsed scenarios.

    Groups scenarios by source file and generates one test file per source.
    Returns a dict mapping output filename to generated code.
    """
    generated_dir = project_root / ".spec-eng" / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # Group scenarios by source file
    groups: dict[str, list[Scenario]] = {}
    for s in parse_result.scenarios:
        key = s.source_file or "unnamed"
        groups.setdefault(key, []).append(s)

    generator = PytestGenerator()
    results: dict[str, str] = {}

    for source_file, scenarios in groups.items():
        # Derive module name from source file
        module_name = Path(source_file).stem if source_file != "unnamed" else "unnamed"
        test_filename = f"test_{module_name}.py"
        code = generator.generate_test_file(scenarios, module_name)

        output_path = generated_dir / test_filename
        output_path.write_text(code)
        results[test_filename] = code

    return results
