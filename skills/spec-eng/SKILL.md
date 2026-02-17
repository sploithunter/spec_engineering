# Spec Engineering — ATDD Workflow

You are orchestrating the spec-eng Acceptance Test-Driven Development workflow. This is an 8-step process that goes from feature intent to verified, passing tests.

## Non-Negotiable Rules

1. **Never modify `.gwt` files without explicit user permission.** Always show proposed changes and wait for approval.
2. **Never modify generated test files.** Always regenerate from specs.
3. **Generated files are gitignored.** They live in `.spec-eng/generated/`.
4. **Both test streams must pass before pushing.** Acceptance tests (from specs) AND unit tests.
5. **Specs describe external observables only.** No implementation details, no class names, no database terms, no API routes.
6. **The parser is real.** Do not generate a parser — use the `parse_gwt` MCP tool.
7. **Tests must be complete.** No stubs, no TODOs, no `pytest.skip()`. Use `xfail` for specs awaiting implementation.

---

## Step 1: Understand the Feature

Ask the user clarifying questions:
- What is the feature? What problem does it solve?
- Who are the actors? (user, admin, system, external service)
- What are the key scenarios? (happy path, error cases, edge cases)
- What domain language should the specs use?
- What is out of scope?

Do NOT proceed until you have a clear understanding. Document the answers.

---

## Step 2: Write GWT Specs

Create `.gwt` files in the `specs/` directory using this format:

```
;===============================================================
; Descriptive scenario title.
;===============================================================
GIVEN precondition describing initial state.

WHEN action or event occurs.

THEN expected observable outcome.
```

Guidelines:
- One file per feature area (e.g., `specs/authentication.gwt`)
- Use domain language, not implementation language
- Each scenario is independent and self-contained
- Clauses end with a period
- Multiple GIVEN/WHEN/THEN clauses are allowed per scenario

**USER APPROVAL GATE:** Show all specs to the user and wait for approval before proceeding.

---

## Step 3: Parse and Validate

Call `mcp__spec-eng__parse_gwt` on each `.gwt` file.

Check for:
- Parse errors (syntax issues in the .gwt files)
- Missing clauses (scenarios without GIVEN, WHEN, or THEN)
- Scenario count matches expectations

Fix any parse errors before proceeding.

---

## Step 4: Build State Graph

Call `mcp__spec-eng__build_state_graph` to extract the state machine.

Review:
- **Entry points**: Are these the correct starting states?
- **Terminal states**: Are these the expected end states?
- **Cycles**: Are feedback loops intentional?
- **State count**: Does this match the domain model?

Call `mcp__spec-eng__find_equivalences` to check for duplicate state labels that should be merged.

---

## Step 5: Gap Analysis

Call `mcp__spec-eng__analyze_spec_gaps` to find completeness issues.

Triage each gap with the user:
- **HIGH severity** (contradictions, unreachable states): Must be resolved before proceeding
- **MEDIUM severity** (dead ends, missing negatives): Discuss with user — may need new specs or may be intentional
- **LOW severity** (missing error paths): Suggest but don't block

For gaps marked "needs-spec", write new scenarios and return to Step 3.

---

## Step 6: Generate Tests (AI-Powered)

Invoke the `test-generator` agent to create complete, runnable test files.

The agent will:
1. Read the parsed specs (structured scenarios)
2. Read the project source code for context
3. Generate test files with real setup, action, and assertion code
4. Write files to `.spec-eng/generated/`

Verify:
- All test files are syntactically valid
- Test count matches scenario count
- No stubs or TODOs remain

---

## Step 7: Implement with TDD

Now implement the feature code using Test-Driven Development:

1. **Run acceptance tests** — they should all fail (red)
2. **Pick one failing acceptance test**
3. **Write a unit test** for the smallest piece needed
4. **Implement** just enough code to pass the unit test
5. **Refactor** if needed
6. **Run both streams** — check progress
7. **Repeat** until all acceptance tests pass

Both test streams (acceptance + unit) must be green before considering the feature done.

---

## Step 8: Review Specs

Invoke the `spec-guardian` agent to check for implementation leakage.

During implementation, it's common to accidentally introduce implementation details into specs (especially if specs were updated during Step 7). The guardian catches:
- Class names and technical identifiers
- Database and API terms
- Framework-specific language

If issues are found, propose rewrites to the user and return to Step 2 if specs change.

---

## Workflow State

Track progress through these steps. If any step fails or produces issues, loop back to the appropriate earlier step rather than pushing forward with known problems.

The goal is: **specs that are pure behavioral descriptions, a complete state machine, no analysis gaps, and two green test streams.**
