# AGENTS.md — Dual-spec GWT⇄DAL compiler + spec-guardian implementation

## Mission
Implement a dual-spec workflow:
- Humans author **GWT** (Given/When/Then) because it’s readable.
- Codex + generators operate on **DAL** because it’s structured.
- The system enforces mutual understanding via a roundtrip check:
  - GWT → DAL → canonical GWT
  - Compare canonical GWT to original GWT via IR equivalence + a readable diff.

## Non-negotiable constraints
- Do not introduce placeholder behavior. Every CLI path must do something real and testable.
- Preserve existing repo conventions and avoid new heavy dependencies unless absolutely necessary.
- Add tests for every new subsystem: vocab loading, parsing, rendering, canonicalization, roundtrip equivalence, and leakage linting.
- Generated files MUST be clearly marked as generated and should be stable across runs (idempotent).
- Prefer deterministic transforms (compiler-like). Use LLM rewriting only as optional “suggestion text,” never as the source of truth.

## Required deliverables
1) A vocab-driven parser for:
   - GWT specs (*.txt) using regex matchers defined in specs/vocab.yaml
   - DAL specs (*.dal) using a strict grammar (statements end in '.')
2) A canonical IR representation (JSON-serializable) that both parsers compile into.
3) A renderer that can emit:
   - canonical DAL from IR
   - canonical GWT from IR
4) A roundtrip command:
   - compile --in specs/foo.txt → produces specs/foo.dal + specs/foo.txt.canonical + ir/foo.json + diff report
   - compile --in specs/foo.dal → produces specs/foo.txt.canonical + ir/foo.json
5) A spec-check command (spec guardian):
   - flags implementation leakage using banned tokens/regex from specs/vocab.yaml
   - reports violations with file/line/column and actionable rewrite suggestions

## Verification rules (Codex must run these)
- Run the repo’s standard test suite and ensure it’s green.
- Add golden/fixture tests that prove:
  - DAL → IR → DAL is idempotent
  - GWT → IR equals DAL → IR for equivalent specs
  - GWT → DAL → canonical GWT produces stable canonical output across repeated runs
