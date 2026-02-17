# CLAUDE.md — spec-eng project context

## What this project is

spec-eng is a Claude Code plugin and CLI tool for Acceptance Test-Driven Development (ATDD) using Given/When/Then behavioral specifications.

## Key architecture

- `src/spec_eng/` — Python library with recursive descent parser, state machine extraction, gap analysis, and test generation
- `src/spec_eng/mcp_server.py` — FastMCP server exposing 8 tools for Claude Code integration
- `.claude-plugin/` — Plugin metadata for Claude Code
- `agents/` — Agent definitions (test-generator, spec-guardian, pipeline-builder)
- `commands/` — Slash commands (/spec-eng, /spec-check, /spec-graph, /spec-gaps)
- `skills/` — ATDD workflow orchestration (8-step process)
- `hooks/` — Event hooks for workflow enforcement

## ATDD workflow

The core workflow is: write specs -> parse -> graph -> gap analysis -> generate tests -> implement -> verify. Specs live in `specs/*.gwt`. Generated tests go in `.spec-eng/generated/` (gitignored).

## Rules

- Never modify .gwt files without user permission
- Never modify generated test files — regenerate from specs
- Specs describe external observables only — no implementation details
- Both test streams (acceptance + unit) must pass before pushing
- The parser is a real recursive descent parser — do not replace it with prompts

## Running tests

```bash
pytest tests/ -q          # All tests
pytest -m unit            # Unit tests only
pytest -m acceptance      # Acceptance tests only
pytest -m e2e             # End-to-end tests only
```

## Linting

```bash
ruff check src/
mypy src/
```
