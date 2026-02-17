"""Click CLI entry point for spec-eng."""

from __future__ import annotations

import re
from pathlib import Path

import click

from spec_eng import __version__
from spec_eng.config import (
    detect_framework,
    detect_language,
    is_initialized,
    load_config,
    save_config,
)
from spec_eng.models import Gap, ProjectConfig


@click.group()
@click.version_option(version=__version__, prog_name="spec-eng")
@click.option("--non-interactive", is_flag=True, default=False, help="Non-interactive mode")
@click.pass_context
def cli(ctx: click.Context, non_interactive: bool) -> None:
    """Spec Engineering: from intent to verified behavioral specifications."""
    ctx.ensure_object(dict)
    ctx.obj["non_interactive"] = non_interactive


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize a project for spec engineering."""
    project_root = Path.cwd()
    already = is_initialized(project_root)
    non_interactive = ctx.obj.get("non_interactive", False)

    if already:
        click.echo("Warning: Project is already initialized. Updating configuration.")

    # Detect language and framework
    languages = detect_language(project_root)
    language = ""
    framework = ""

    if languages:
        if len(languages) == 1:
            language = languages[0]
        else:
            if non_interactive:
                language = languages[0]
            else:
                click.echo(f"Detected languages: {', '.join(languages)}")
                click.echo("Select a primary language or configure both.")
                language = languages[0]  # Default to first
        framework = detect_framework(project_root, language)

        if not non_interactive:
            click.echo(f"Detected language: {language}")
            click.echo(f"Detected framework: {framework}")

    # Load existing config or create new
    if already:
        config = load_config(project_root)
        config.language = language or config.language
        config.framework = framework or config.framework
    else:
        config = ProjectConfig(language=language, framework=framework)

    # Create directories
    spec_eng_dir = project_root / ".spec-eng"
    spec_eng_dir.mkdir(exist_ok=True)
    specs_dir = project_root / "specs"
    specs_dir.mkdir(exist_ok=True)

    save_config(config, project_root)

    if already:
        click.echo("Configuration updated. Existing spec files preserved.")
    else:
        click.echo("Initialized spec engineering project.")
        click.echo(f"  Created: {spec_eng_dir}/")
        click.echo(f"  Created: {specs_dir}/")
        click.echo(f"  Config:  {spec_eng_dir / 'config.json'}")


@cli.command()
@click.argument("description")
@click.pass_context
def draft(ctx: click.Context, description: str) -> None:
    """Draft GWT specs from a description using AI."""
    from spec_eng.ai import AIError, draft_specs

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized. Run `spec-eng init` first.")
        ctx.exit(1)
        return

    non_interactive = ctx.obj.get("non_interactive", False)

    try:
        scenarios = draft_specs(description)
    except AIError as e:
        click.echo(f"AI error: {e}")
        ctx.exit(1)
        return

    if not scenarios:
        click.echo("No scenarios generated.")
        return

    click.echo(f"Generated {len(scenarios)} scenario(s):\n")
    specs_dir = project_root / "specs"
    specs_dir.mkdir(exist_ok=True)

    saved_count = 0
    for i, scenario in enumerate(scenarios, 1):
        click.echo(f"  {i}. {scenario.title}")
        for g in scenario.givens:
            click.echo(f"     GIVEN {g.text}.")
        for w in scenario.whens:
            click.echo(f"     WHEN {w.text}.")
        for t in scenario.thens:
            click.echo(f"     THEN {t.text}.")
        click.echo()

        if non_interactive:
            approved = True
        else:
            approved = click.confirm("  Save this scenario?", default=True)

        if approved:
            slug = _slugify(scenario.title or f"draft-{i}")
            target = specs_dir / f"{slug}.gwt"
            bar = ";==============================================================="
            content = f"{bar}\n; {scenario.title}\n{bar}\n"
            for g in scenario.givens:
                content += f"GIVEN {g.text}.\n"
            content += "\n"
            for w in scenario.whens:
                content += f"WHEN {w.text}.\n"
            content += "\n"
            for t in scenario.thens:
                content += f"THEN {t.text}.\n"

            if target.exists():
                with open(target, "a") as f:
                    f.write("\n" + content)
            else:
                target.write_text(content)
            saved_count += 1

    click.echo(f"\nSaved {saved_count} of {len(scenarios)} scenario(s).")


@cli.command()
@click.argument("description")
@click.pass_context
def new(ctx: click.Context, description: str) -> None:
    """Create a new spec file from a description."""
    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Project is not initialized. Run `spec-eng init` first.")
        ctx.exit(1)
        return

    # Generate filename slug from description
    slug = _slugify(description)
    specs_dir = project_root / "specs"
    specs_dir.mkdir(exist_ok=True)

    gwt_file = specs_dir / f"{slug}.gwt"
    if gwt_file.exists():
        click.echo(f"Warning: {gwt_file} already exists. Skipping.")
        return

    # Write scaffold template
    bar = ";==============================================================="
    content = f"""{bar}
; {description}.
{bar}
GIVEN <precondition>.

WHEN <action>.

THEN <expected result>.
"""
    gwt_file.write_text(content)
    click.echo(f"Created: {gwt_file}")


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["json", "dot"]), default=None)
@click.option("--file", "file_path", type=click.Path(exists=True), default=None)
@click.pass_context
def graph(ctx: click.Context, fmt: str | None, file_path: str | None) -> None:
    """Build and display the state machine graph from specs."""
    import json as json_mod

    from spec_eng.exporters.dot import export_dot
    from spec_eng.exporters.json_export import export_json
    from spec_eng.graph import build_graph, graph_to_json
    from spec_eng.parser import parse_gwt_file, parse_markdown_gwt

    project_root = Path.cwd()

    if file_path:
        p = Path(file_path)
        if p.suffix == ".md":
            result = parse_markdown_gwt(p)
        else:
            result = parse_gwt_file(p)
    else:
        if not is_initialized(project_root):
            click.echo("Error: Project is not initialized. Run `spec-eng init` first.")
            ctx.exit(1)
            return

        from spec_eng.models import ParseResult

        specs_dir = project_root / "specs"
        all_scenarios: list = []
        all_errors: list = []
        for gwt_file in sorted(specs_dir.glob("*.gwt")):
            r = parse_gwt_file(gwt_file)
            all_scenarios.extend(r.scenarios)
            all_errors.extend(r.errors)
        result = ParseResult(scenarios=all_scenarios, errors=all_errors)

    if not result.scenarios:
        click.echo("No scenarios found.")
        return

    gm = build_graph(result)

    # Save graph
    spec_eng_dir = project_root / ".spec-eng"
    spec_eng_dir.mkdir(exist_ok=True)
    graph_json_path = spec_eng_dir / "graph.json"
    graph_json_path.write_text(json_mod.dumps(graph_to_json(gm), indent=2))

    if fmt == "dot":
        click.echo(export_dot(gm))
    elif fmt == "json":
        click.echo(export_json(gm))
    else:
        click.echo(
            f"Graph built: {len(gm.states)} states, "
            f"{len(gm.transitions)} transitions"
        )
        if gm.entry_points:
            click.echo(f"Entry points: {', '.join(gm.entry_points)}")
        if gm.terminal_states:
            click.echo(f"Terminal states: {', '.join(gm.terminal_states)}")
        if gm.cycles:
            click.echo(f"Cycles detected: {len(gm.cycles)}")


@cli.command()
@click.option("--suggest", is_flag=True, default=False, help="AI-suggest fixes")
@click.pass_context
def gaps(ctx: click.Context, suggest: bool) -> None:
    """Analyze the state machine graph for completeness gaps."""
    from spec_eng.gaps import analyze_gaps, load_triaged, save_gaps
    from spec_eng.graph import build_graph
    from spec_eng.parser import parse_gwt_file

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized. Run `spec-eng init` first.")
        ctx.exit(1)
        return

    # Parse all specs
    specs_dir = project_root / "specs"
    from spec_eng.models import ParseResult

    all_scenarios: list = []
    for gwt_file in sorted(specs_dir.glob("*.gwt")):
        r = parse_gwt_file(gwt_file)
        all_scenarios.extend(r.scenarios)

    if not all_scenarios:
        click.echo("No scenarios found. Write specs first.")
        return

    gm = build_graph(ParseResult(scenarios=all_scenarios))
    triaged = load_triaged(project_root)
    gap_list = analyze_gaps(gm, triaged)
    save_gaps(gap_list, project_root)

    if not gap_list:
        click.echo("No gaps found.")
        return

    click.echo(f"Found {len(gap_list)} gap(s):")
    for g in gap_list:
        click.echo(f"  [{g.severity.value.upper()}] {g.gap_type.value}: {g.description}")
        click.echo(f"    ? {g.question.split(chr(10))[0]}")

    if suggest:
        click.echo("\nAI suggestions require `spec-eng gaps --suggest` with API key.")


@cli.command()
@click.pass_context
def triage(ctx: click.Context) -> None:
    """Triage gaps interactively."""
    from spec_eng.gaps import load_gaps, save_gaps

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    gap_list = load_gaps(project_root)
    untriaged = [g for g in gap_list if g.triage_status is None]

    if not untriaged:
        click.echo("No untriaged gaps.")
        return

    non_interactive = ctx.obj.get("non_interactive", False)

    for i, g in enumerate(untriaged, 1):
        click.echo(f"\nGap {i}/{len(untriaged)}:")
        click.echo(f"  Type: {g.gap_type.value}")
        click.echo(f"  {g.description}")
        click.echo(f"  ? {g.question.split(chr(10))[0]}")

        if non_interactive:
            g.triage_status = "needs-spec"
        else:
            choice = click.prompt(
                "  Action",
                type=click.Choice(["needs-spec", "intentional", "out-of-scope"]),
                default="needs-spec",
            )
            g.triage_status = choice

        if g.triage_status == "needs-spec":
            _generate_gap_template(g, project_root)

    save_gaps(gap_list, project_root)
    click.echo(f"\nTriaged {len(untriaged)} gap(s).")


def _generate_gap_template(gap: Gap, project_root: Path) -> None:
    """Generate a GWT template for a gap triaged as 'needs-spec'."""

    specs_dir = project_root / "specs"
    specs_dir.mkdir(exist_ok=True)

    # Find relevant spec file or create new one
    state = gap.states[0] if gap.states else "unknown"
    slug = _slugify(state)
    target = specs_dir / f"{slug}.gwt"

    bar = ";==============================================================="
    template = f"""
{bar}
; TODO: Address gap - {gap.description}
{bar}
GIVEN {state}.

WHEN <error or missing event>.

THEN <expected outcome>.
"""
    # Append to existing file or create new
    if target.exists():
        with open(target, "a") as f:
            f.write(template)
        click.echo(f"  Appended template to {target}")
    else:
        target.write_text(template.lstrip())
        click.echo(f"  Created {target}")


@cli.command()
@click.option("--refresh", is_flag=True, default=False, help="Re-bootstrap pipeline")
@click.pass_context
def bootstrap(ctx: click.Context, refresh: bool) -> None:
    """Bootstrap the parser/generator pipeline."""
    from spec_eng.pipeline import bootstrap_pipeline

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized. Run `spec-eng init` first.")
        ctx.exit(1)
        return

    summary = bootstrap_pipeline(project_root, refresh=refresh)
    click.echo(f"Pipeline bootstrapped for {summary['language']}/{summary['framework']}")
    click.echo(f"  Pipeline dir: {summary['pipeline_dir']}")
    click.echo(f"  Validation: {summary['validation']}")


@cli.command("parse")
@click.option("--inspect", is_flag=True, default=False, help="Display IR in readable format")
@click.pass_context
def parse_cmd(ctx: click.Context, inspect: bool) -> None:
    """Parse GWT spec files and produce JSON IR."""
    import json as json_mod

    from spec_eng.generator import generate_ir
    from spec_eng.parser import parse_gwt_file

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    from spec_eng.models import ParseResult

    specs_dir = project_root / "specs"
    all_scenarios: list = []
    all_errors: list = []
    for gwt_file in sorted(specs_dir.glob("*.gwt")):
        r = parse_gwt_file(gwt_file)
        all_scenarios.extend(r.scenarios)
        all_errors.extend(r.errors)

    result = ParseResult(scenarios=all_scenarios, errors=all_errors)

    if result.errors:
        for e in result.errors:
            click.echo(f"Error: {e.source_file}:{e.line_number}: {e.message}")

    if not result.scenarios:
        click.echo("No scenarios found.")
        return

    ir = generate_ir(result)

    # Save IR
    ir_dir = project_root / ".spec-eng"
    ir_dir.mkdir(exist_ok=True)
    ir_path = ir_dir / "ir.json"
    ir_path.write_text(json_mod.dumps(ir, indent=2))

    file_count = len(list(specs_dir.glob("*.gwt")))
    click.echo(f"Parsed {len(result.scenarios)} scenario(s) from {file_count} file(s).")

    if inspect:
        for entry in ir:
            click.echo(f"\n  Scenario: {entry['title']}")
            click.echo(f"  Source: {entry['source_file']}:{entry['line_number']}")
            for g in entry["givens"]:
                click.echo(f"    GIVEN {g['text']}.")
            for w in entry["whens"]:
                click.echo(f"    WHEN {w['text']}.")
            for t in entry["thens"]:
                click.echo(f"    THEN {t['text']}.")


@cli.command()
@click.pass_context
def generate(ctx: click.Context) -> None:
    """Generate test files from parsed GWT specs."""
    from spec_eng.generator import generate_tests
    from spec_eng.parser import parse_gwt_file

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    from spec_eng.models import ParseResult

    specs_dir = project_root / "specs"
    all_scenarios: list = []
    for gwt_file in sorted(specs_dir.glob("*.gwt")):
        r = parse_gwt_file(gwt_file)
        all_scenarios.extend(r.scenarios)

    if not all_scenarios:
        click.echo("No scenarios found. Write specs first.")
        return

    result = ParseResult(scenarios=all_scenarios)
    generated = generate_tests(project_root, result)

    generated_dir = project_root / ".spec-eng" / "generated"
    click.echo(f"Generated {len(generated)} test file(s) in {generated_dir}/")
    for name in sorted(generated):
        click.echo(f"  {name}")

    # Check .gitignore advice
    gitignore = project_root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        if ".spec-eng/generated/" not in content:
            click.echo("\nNote: Consider adding .spec-eng/generated/ to .gitignore")
    else:
        click.echo("\nNote: Generated files should be gitignored.")


@cli.command()
@click.option("--target", default=None, help="Target language for tests")
@click.pass_context
def test(ctx: click.Context, target: str | None) -> None:
    """Run generated acceptance tests."""
    from spec_eng.runner import run_acceptance_tests

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    specs_dir = project_root / "specs"
    if not specs_dir.exists() or not list(specs_dir.glob("*.gwt")):
        click.echo("Warning: No spec files found.")
        click.echo("Suggestion: Run `spec-eng new` or `spec-eng draft` to create specs.")
        return

    result = run_acceptance_tests(project_root)
    click.echo(result.output)

    if result.failing_tests:
        click.echo("\nFailing tests:")
        for t in result.failing_tests:
            click.echo(f"  {t}")

    if not result.success:
        ctx.exit(1)


@cli.command()
@click.pass_context
def verify(ctx: click.Context) -> None:
    """Run both acceptance and unit tests (dual stream verification)."""
    from spec_eng.runner import run_verify

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    result = run_verify(project_root)
    click.echo(result.output)

    if result.failing_tests:
        click.echo("\nFailing tests:")
        for t in result.failing_tests:
            click.echo(f"  {t}")

    if not result.success:
        click.echo("\nVerification FAILED.")
        ctx.exit(1)
    else:
        click.echo("\nVerification PASSED.")


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show the current state of the project."""
    from spec_eng.gaps import load_gaps
    from spec_eng.parser import parse_gwt_file
    from spec_eng.pipeline import is_bootstrapped

    project_root = Path.cwd()
    if not is_initialized(project_root):
        click.echo("Project is not initialized. Run `spec-eng init`.")
        return

    specs_dir = project_root / "specs"

    # Count specs and scenarios
    spec_files = list(specs_dir.glob("*.gwt")) if specs_dir.exists() else []
    scenario_count = 0
    for f in spec_files:
        r = parse_gwt_file(f)
        scenario_count += len(r.scenarios)

    click.echo(f"Spec files: {len(spec_files)}")
    click.echo(f"Scenarios: {scenario_count}")

    # Graph info
    graph_path = project_root / ".spec-eng" / "graph.json"
    if graph_path.exists():
        import json as json_mod

        data = json_mod.loads(graph_path.read_text())
        click.echo(
            f"Graph: {len(data.get('states', {}))} states, "
            f"{len(data.get('transitions', []))} transitions"
        )
    else:
        click.echo("Graph: not built")

    # Gap info
    gap_list = load_gaps(project_root)
    unresolved = [g for g in gap_list if g.triage_status is None]
    click.echo(f"Gaps: {len(unresolved)} unresolved")

    # Pipeline
    bootstrapped = is_bootstrapped(project_root)
    pipeline_status = "bootstrapped" if bootstrapped else "not bootstrapped"
    click.echo(f"Pipeline: {pipeline_status}")

    # Last test results
    gen_dir = project_root / ".spec-eng" / "generated"
    if gen_dir.exists() and list(gen_dir.glob("test_*.py")):
        click.echo("Generated tests: present")
    else:
        click.echo("Generated tests: none")


@cli.command("ci")
@click.pass_context
def ci_cmd(ctx: click.Context) -> None:
    """Run full verification pipeline for CI (non-interactive)."""
    from spec_eng.gaps import analyze_gaps, load_triaged, save_gaps
    from spec_eng.generator import generate_tests
    from spec_eng.graph import build_graph
    from spec_eng.parser import parse_gwt_file
    from spec_eng.runner import run_acceptance_tests, run_unit_tests

    project_root = Path.cwd()
    ctx.obj["non_interactive"] = True

    if not is_initialized(project_root):
        click.echo("Error: Not initialized.")
        ctx.exit(1)
        return

    specs_dir = project_root / "specs"
    from spec_eng.models import ParseResult

    # Step 1: Parse
    click.echo("Parsing specs...")
    all_scenarios: list = []
    all_errors: list = []
    for gwt_file in sorted(specs_dir.glob("*.gwt")):
        r = parse_gwt_file(gwt_file)
        all_scenarios.extend(r.scenarios)
        all_errors.extend(r.errors)

    if all_errors:
        for e in all_errors:
            click.echo(f"  Parse error: {e.message}")
        ctx.exit(1)
        return

    if not all_scenarios:
        click.echo("No scenarios found.")
        ctx.exit(1)
        return

    result = ParseResult(scenarios=all_scenarios)
    click.echo(f"  {len(all_scenarios)} scenario(s) parsed.")

    # Step 2: Build graph
    click.echo("Building graph...")
    gm = build_graph(result)
    click.echo(f"  {len(gm.states)} states, {len(gm.transitions)} transitions.")

    # Step 3: Gap analysis
    click.echo("Analyzing gaps...")
    triaged = load_triaged(project_root)
    gap_list = analyze_gaps(gm, triaged)
    save_gaps(gap_list, project_root)

    critical = [g for g in gap_list if g.severity.value == "high"]
    if critical:
        click.echo(f"  {len(critical)} critical gap(s) found!")
        for g in critical:
            click.echo(f"    {g.gap_type.value}: {g.description}")
        ctx.exit(1)
        return
    click.echo(f"  {len(gap_list)} gap(s), 0 critical.")

    # Step 4: Generate tests
    click.echo("Generating tests...")
    generated = generate_tests(project_root, result)
    click.echo(f"  {len(generated)} test file(s) generated.")

    # Step 5: Run acceptance tests
    click.echo("Running acceptance tests...")
    acc = run_acceptance_tests(project_root)
    click.echo(f"  {acc.passed} passed, {acc.failed} failed, {acc.skipped} skipped.")

    # Step 6: Run unit tests
    click.echo("Running unit tests...")
    unit = run_unit_tests(project_root)
    click.echo(f"  {unit.passed} passed, {unit.failed} failed.")

    # Final verdict
    if acc.success and (unit.success or unit.total == 0):
        click.echo("\nCI: PASSED")
    else:
        click.echo("\nCI: FAILED")
        ctx.exit(1)


def _slugify(text: str) -> str:
    """Convert a description to a filename slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = slug.strip("-")
    return slug
