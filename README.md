# spec-eng

A CLI tool for **Spec Engineering** — progressive refinement from human intent to verified behavioral specifications using Given/When/Then (GWT) format.

`spec-eng` extracts state machines from GWT specs, performs gap analysis to find missing scenarios, generates test scaffolds, and optionally uses AI (Anthropic Claude) for spec drafting and suggestions.

## Why

Most teams write tests after code. Spec Engineering flips this: you write behavioral specifications first, then use them to drive implementation. The tool enforces a clean separation between *what* the system does (specs) and *how* it does it (code).

- **Specs are portable** — the same `.gwt` files work across Python, TypeScript, Rust, or any target
- **The Spec Guardian** catches implementation details leaking into your specs (class names, database terms, API paths)
- **Gap analysis** finds missing scenarios before you write a single line of code
- **Self-hosting** — `spec-eng` can parse and analyze its own specification

## Install

```bash
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Quick Start

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

## Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize a project for spec engineering |
| `new` | Create a new spec file from a description |
| `draft` | AI-assisted spec drafting (requires Anthropic API key) |
| `graph` | Extract state machine from specs |
| `gaps` | Analyze graph for missing scenarios |
| `triage` | Triage detected gaps |
| `bootstrap` | Set up the test generation pipeline |
| `parse` | Parse all specs into intermediate representation |
| `generate` | Generate test scaffolds from IR |
| `test` | Run generated acceptance tests |
| `verify` | Run both acceptance and unit test streams |
| `status` | Show project overview |
| `ci` | Non-interactive full pipeline for CI |

## The Pipeline

```
write specs (.gwt)
    → parse (recursive descent)
    → graph (state machine extraction)
    → gaps (completeness analysis)
    → iterate (write more specs)
    → bootstrap + generate (test scaffolds)
    → implement (fill in TODOs)
    → verify (both test streams pass)
```

## Spec Guardian

The guardian detects implementation details in your specs:

```
⚠ "GIVEN the UserService is initialized"
  → Suggests: "GIVEN the system is ready to register users"

⚠ "WHEN a POST request is sent to /api/users"
  → Suggests: "WHEN a user submits registration"
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

282 tests covering all 52 acceptance scenarios from the [SPEC](SPEC.md).

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
  exporters/        # DOT and JSON export
```

## License

MIT
