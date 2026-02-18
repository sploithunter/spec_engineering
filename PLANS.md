# PLANS.md — Build dual-spec GWT⇄DAL compiler loop + vocab.yaml-driven lints

## High-level goal
Implement a compiler pipeline that creates synergy between:
- Human-authored, reviewable **GWT**
- Agent-friendly, structured **DAL**
- A canonicalization + equivalence loop that prevents drift

Core invariant:
- DAL is *canonical* at the IR level.
- GWT is a human surface form that is normalized via canonical rendering.
- Equivalence is decided by IR equality, not string equality.

## Inputs you must support
- specs/vocab.yaml (schema already provided in repo/specs)
- specs/*.txt (GWT)
- specs/*.dal (DAL)

## Outputs you must produce
For input specs/<slug>.txt:
- specs/<slug>.dal (generated DAL)
- specs/<slug>.txt.canonical (generated canonical GWT)
- acceptance-pipeline/ir/<slug>.json (canonical IR)
- acceptance-pipeline/roundtrip/<slug>.diff.txt (human-readable diff report)

For input specs/<slug>.dal:
- specs/<slug>.txt.canonical
- acceptance-pipeline/ir/<slug>.json

## Commands / entrypoints
Implement (or wire into existing) CLI or slash-command equivalents:

1) spec-compile
- Usage:
  - spec-compile --in specs/<slug>.txt
  - spec-compile --in specs/<slug>.dal
- Exit codes:
  - 0 on success
  - non-zero on parse/type errors or failed equivalence gates

2) spec-check
- Usage:
  - spec-check --in specs/<slug>.txt
  - spec-check --in specs/<slug>.dal
  - spec-check --in specs/ (directory recursive)
- Exit codes:
  - 0 if no violations
  - non-zero if violations found

## Step-by-step implementation plan

### Step 0 — Repo discovery (do this first)
1) Inspect repo layout; identify the existing command runner / plugin entrypoint(s).
2) Identify the existing acceptance pipeline outputs:
   - acceptance-pipeline/ir/
   - generated-acceptance-tests/
   - runner script(s)
3) Identify existing test framework(s) and how to run them.

Deliverable:
- A brief note in the PR description explaining where you integrated spec-compile + spec-check.

### Step 1 — Define the IR (single source of truth)
Create an internal IR structure like:

FeatureIR:
- feature_id: string
- scenarios: list[ScenarioIR]

ScenarioIR:
- name: string
- imports: list[string]         # for composition
- givens: list[StepIR]          # facts
- whens: list[StepIR]           # actions (usually 1, allow list for future)
- thens: list[StepIR]           # expectations

StepIR:
- kind: "fact" | "action" | "expectation"
- symbol: string                # e.g., "plugin_installed"
- args: dict[string, primitive] # strings/numbers/bools

Rules:
- Preserve statement order as authored, but canonicalize output order deterministically if needed.
- For GWT AND-steps: AND inherits the previous step type (GIVEN/WHEN/THEN).

### Step 2 — Implement vocab.yaml loader + validator
Implement:
- load_yaml("specs/vocab.yaml")
- validate required keys exist:
  - vocabulary.facts/actions/expectations
  - types
  - lints.implementation_leakage
  - gwt.keyword + dal.keyword config (if present)
- compile all regex matchers once at startup (fail fast if invalid)

Deliverable:
- Unit tests: invalid YAML, missing keys, invalid regex => meaningful error.

### Step 3 — DAL parser (strict)
Implement a DAL parser with these rules:
- Ignore blank lines
- Ignore comment lines starting with ';'
- Every statement ends with a trailing '.'
- Supported statements:
  - FEATURE <identifier>.
  - SCENARIO <snake_case_name>.
  - IMPORT <snake_case_name>.
  - FACT <symbol>(<kwargs...>).
  - DO <symbol>(<kwargs...>).
  - EXPECT <symbol>(<kwargs...>).

Arg parsing:
- kwargs are key=value separated by commas
- values support:
  - "double quoted strings"
  - integers
  - true/false

Semantic checks:
- SCENARIO names must match vocab type scenario_name if defined
- FACT/DO/EXPECT symbols must exist in vocab
- args must satisfy types (pattern/enum)

Deliverables:
- parse_dal(file) -> FeatureIR
- render_dal(FeatureIR) -> canonical DAL text
- Tests:
  - DAL → IR → DAL is idempotent (golden snapshot)

### Step 4 — GWT parser (vocab-regex driven)
Implement parsing for GWT files:
- Ignore blank lines
- Ignore comment lines starting with ';'
- Parse step keyword: GIVEN/WHEN/THEN/AND
- Require trailing period (per vocab config)

Matching:
- For each GWT step line, try matching against:
  - facts[*].gwt.match
  - actions[*].gwt.match
  - expectations[*].gwt.match
- When a match succeeds:
  - extract named capture groups into args
  - apply any derive_args_from_context rules if present
  - apply default_args if present

Context:
- Track feature name/slug if derivations exist
- Track last step kind so AND is typed correctly

Unknown line behavior:
- Hard error with:
  - line number
  - the line text
  - “closest candidates” list (by regex name or simple string similarity)

Deliverables:
- parse_gwt(file) -> FeatureIR
- render_gwt(FeatureIR) -> canonical GWT text (uses vocab.gwt.render)
- Tests:
  - Provided sample GWT parses successfully
  - GWT → IR equals DAL → IR for equivalent fixtures

### Step 5 — Canonicalization + roundtrip gate
Implement compile pipeline:

Given input_path:

If input is .txt (GWT):
1) IR = parse_gwt(input)
2) canonical_dal = render_dal(IR)
3) canonical_gwt = render_gwt(IR)
4) Write:
   - specs/<slug>.dal
   - specs/<slug>.txt.canonical
   - acceptance-pipeline/ir/<slug>.json
5) Produce a human-readable diff report between:
   - original GWT and canonical GWT
   - (use a stable unified diff)
6) Gate:
   - If IR computed from original GWT != IR computed from canonical GWT, fail (this indicates non-idempotent rendering/parsing)
   - Otherwise pass (even if the text differs)

If input is .dal:
1) IR = parse_dal(input)
2) canonical_gwt = render_gwt(IR)
3) Write:
   - specs/<slug>.txt.canonical
   - acceptance-pipeline/ir/<slug>.json

### Step 6 — spec-check (spec guardian)
Implement spec-check using vocab lints:
- banned_tokens (case-insensitive whole-word matching)
- banned_regex patterns
- For each violation:
  - report file, line, column, token/regex hit
  - include rewrite suggestion when possible

Rewrite suggestions:
- Prefer deterministic suggestions:
  - If line contains "UserService" or "repository": suggest the canonical step "GIVEN no registered users."
  - If line contains HTTP verbs or /api/...: suggest canonical domain action wording
- Suggestions can come from vocab entries:
  - e.g., expectations/spec_check_suggests_rewrite render templates

Exit behavior:
- non-zero if any violations found

### Step 7 — Wire into acceptance pipeline
Locate existing “pipeline generation” entrypoint.
Change it so:
- It consumes acceptance-pipeline/ir/<slug>.json produced by spec-compile,
  rather than trying to infer structure directly from raw GWT.
- It remains capable of generating runnable acceptance tests.

Minimum viable integration:
- spec-compile runs first
- pipeline generation consumes the IR output

### Step 8 — Add fixtures + golden tests
Add fixtures under a stable test folder:
- specs/atdd-dual-spec-mode.txt
- specs/atdd-dual-spec-mode.dal
- specs/vocab.yaml

Golden outputs:
- specs/atdd-dual-spec-mode.txt.canonical
- acceptance-pipeline/ir/atdd-dual-spec-mode.json

Tests must assert:
- parse/render stability
- roundtrip gate passes
- spec-check flags leakage examples

### Step 9 — Docs
Update README or docs to explain:
- Why dual-spec exists (human vs agent)
- Which file is authoritative in which workflow
- How to run spec-compile and spec-check
- How to interpret canonical diffs

## Definition of done
- Running spec-compile on provided fixtures produces stable outputs across runs.
- Roundtrip gates are enforced.
- spec-check reliably flags implementation leakage patterns from vocab.yaml.
- Repo tests pass.
