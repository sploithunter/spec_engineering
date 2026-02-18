# spec-eng

A **Claude Code plugin** and CLI tool for **Spec Engineering** — progressive refinement from human intent to verified behavioral specifications using Given/When/Then (GWT) format.

`spec-eng` provides a real recursive descent parser, state machine extraction, automated gap analysis, and AI-powered test generation. Use it as a standalone CLI or as a Claude Code plugin for the full ATDD workflow.

## Why

Most teams write tests after code. Spec Engineering flips this: you write behavioral specifications first, then use them to drive implementation. The tool enforces a clean separation between *what* the system does (specs) and *how* it does it (code).

- **Specs are portable** — the same `.gwt` files work across Python, TypeScript, Rust, or any target
- **The Spec Guardian** catches implementation details leaking into your specs (class names, database terms, API paths)
- **Gap analysis** finds missing scenarios before you write a single line of code
- **AI-powered test generation** produces complete, runnable tests — not stubs with TODOs
- **Self-hosting** — `spec-eng` can parse and analyze its own specification

## Install as Claude Code Plugin

```bash
# From the plugin directory
claude plugin install /path/to/spec-eng

# Or install from a cloned repo
cd spec-eng
claude plugin install .
```

This gives you:
- MCP tools: `parse_gwt`, `build_state_graph`, `analyze_spec_gaps`, `check_guardian`, `find_equivalences`, `export_graph`, `detect_project`, `get_project_status`
- Workflow MCP tools: `spec_compile`, `spec_check`, `interrogate`
- Slash commands: `/spec-eng`, `/spec-check`, `/spec-graph`, `/spec-gaps`
- Agents: test-generator, spec-guardian, pipeline-builder
- Hooks: spec-exists warnings and stop reminders

## Install as CLI

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Standalone MCP (Workflow)

For direct MCP attachment (outside Claude plugin packaging):

```bash
spec-eng-workflow-mcp
```

Config example:

```json
{
  "spec-eng-workflow": {
    "command": "spec-eng-workflow-mcp",
    "args": []
  }
}
```

Use `.mcp.workflow.json` in this repo as a template.

## Web API

Run a lightweight HTTP API for remote automation:

```bash
spec-eng-web --host 127.0.0.1 --port 8765 --project-root .
```

Endpoints:
- `GET /health`
- `POST /compile` with `{\"input_path\": \"specs/foo.txt\"}`
- `POST /check` with `{\"input_path\": \"specs/foo.txt\"}`
- `POST /interrogate` with `{\"idea\": \"...\", \"answers\": [\"k=v\", ...], \"approve\": false}`

## Quick Start (Plugin)

```
/spec-eng user authentication with email and password
```

This walks you through the full 8-step ATDD workflow:
1. Understand the feature
2. Write GWT specs
3. Parse and validate
4. Build state graph
5. Gap analysis
6. Generate complete tests
7. Implement with TDD
8. Review specs

## Quick Start (CLI)

```bash
# Initialize a new project
spec-eng init

# Create a spec file
spec-eng new "User registration"

# Edit specs/user-registration.gwt with your scenarios, then:
spec-eng graph          # Extract state machine
spec-eng gaps           # Find missing scenarios
spec-eng bootstrap      # Set up test pipeline
spec-eng parse          # Parse all specs to IR
spec-eng generate       # Generate test scaffolds
spec-eng test           # Run generated tests
spec-eng verify         # Verify both test streams
spec-eng status         # See project overview
spec-eng ci             # Full pipeline for CI
```

## GWT Format

Specs use a simple Given/When/Then format with `;===` headers:

```
;===============================================================
; User can register with email and password.
;===============================================================
GIVEN no registered users.

WHEN a user registers with a valid email and password.

THEN there is 1 registered user.
THEN the user receives a confirmation email.

;===============================================================
; Registration fails with an already-taken email.
;===============================================================
GIVEN there is 1 registered user.

WHEN another user registers with the same email.

THEN registration fails with a duplicate email error.
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/spec-eng` | Start full ATDD workflow for a feature |
| `/spec-check` | Audit specs for implementation leakage |
| `/spec-graph` | Build and display state machine graph |
| `/spec-gaps` | Run gap analysis, present findings |

## MCP Tools

| Tool | Purpose |
|------|---------|
| `parse_gwt` | Parse .gwt files into structured scenarios |
| `build_state_graph` | Extract state machine from scenarios |
| `analyze_spec_gaps` | Find dead ends, unreachable states, contradictions |
| `check_guardian` | Detect implementation detail leakage |
| `find_equivalences` | Detect duplicate/similar state labels |
| `export_graph` | Export graph as DOT or JSON |
| `detect_project` | Detect project language and framework |
| `get_project_status` | Spec count, graph size, gap count, pipeline state |
| `spec_compile` | Compile dual-spec artifacts (`.dal`, canonical GWT, IR, diff) |
| `spec_check` | Vocab-driven leakage checks for `.txt`/`.dal` |
| `interrogate` | Deterministic interrogation iteration with compile/check loop |

## CLI Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize a project for spec engineering |
| `new` | Create a new spec file from a description |
| `draft` | AI-assisted spec drafting (requires Anthropic API key) |
| `interrogate` | Deterministic idea-to-spec interrogation loop |
| `graph` | Extract state machine from specs |
| `gaps` | Analyze graph for missing scenarios |
| `triage` | Triage detected gaps |
| `bootstrap` | Set up the test generation pipeline |
| `parse` | Parse all specs into intermediate representation |
| `spec-compile` | Compile and normalize dual-spec artifacts |
| `spec-check` | Run vocab-driven leakage checks |
| `generate` | Generate test scaffolds from IR |
| `test` | Run generated acceptance tests |
| `verify` | Run both acceptance and unit test streams |
| `status` | Show project overview |
| `ci` | Non-interactive full pipeline for CI |

## The Pipeline

```
write specs (.gwt)
    -> parse (recursive descent)
    -> graph (state machine extraction)
    -> gaps (completeness analysis)
    -> iterate (write more specs)
    -> generate tests (AI-powered, complete & runnable)
    -> implement (TDD red-green-refactor)
    -> verify (both test streams pass)
```

## Spec Guardian

The guardian detects implementation details in your specs:

```
  "GIVEN the UserService is initialized"
  -> Suggests: "GIVEN the system is ready to register users"

  "WHEN a POST request is sent to /api/users"
  -> Suggests: "WHEN a user submits registration"
```

Configure sensitivity and allowlists in `.spec-eng/config.json`.

## AI Features

With an `ANTHROPIC_API_KEY` environment variable set:

```bash
# Draft specs from a description
spec-eng draft "User authentication with email, password, and password reset"

# Get AI suggestions for gap fixes
spec-eng gaps --suggest
```

AI features are entirely optional — the core pipeline works fully offline.

## Testing

```bash
# Run all tests
pytest

# Run by category
pytest -m unit          # Unit tests only
pytest -m acceptance    # Acceptance tests only
pytest -m e2e           # End-to-end tests only
```

306 tests covering all 52 acceptance scenarios from the [SPEC](SPEC.md).

## Project Structure

```
src/spec_eng/
  cli.py            # Click CLI entry point
  models.py         # Data models (Scenario, State, Gap, etc.)
  parser.py         # GWT recursive descent parser
  guardian.py       # Spec guardian (implementation detail detection)
  graph.py          # State machine extraction (NetworkX)
  gaps.py           # Gap analysis engine
  generator.py      # Test scaffold generation
  pipeline.py       # Pipeline bootstrapping
  runner.py         # Test execution
  ai.py             # Anthropic Claude integration
  config.py         # Configuration management
  mcp_server.py     # FastMCP server for Claude Code integration
  exporters/        # DOT and JSON export
.claude-plugin/     # Plugin metadata
agents/             # Agent definitions (test-generator, spec-guardian, pipeline-builder)
commands/           # Slash commands
  spec-interrogate.md
  spec-compile.md
skills/             # Workflow skills (ATDD 8-step process)
hooks/              # Event hooks (spec warnings, stop reminders)
web_api.py          # HTTP API server for compile/check/interrogate
workflow_mcp.py     # Standalone workflow-focused MCP server
```

## License

MIT
