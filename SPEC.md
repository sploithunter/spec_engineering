# Spec Engineering: Specification

This document is the specification for the Spec Engineering tool. It is written
in Given/When/Then format. **This document IS the acceptance test suite.** Every
scenario below must pass for the tool to be considered correct.

This document is a living artifact. As gap analysis reveals missing coverage,
new scenarios are appended. Scenarios are never removed -- only marked deprecated
with a reason.

---

## Conventions

- `spec-eng` is the CLI tool name.
- `$PROJECT` refers to the current working directory.
- GWT spec files use the `.gwt` extension and live in `$PROJECT/specs/`.
- The state machine graph is stored as `$PROJECT/.spec-eng/graph.json`.
- The gap analysis report is stored as `$PROJECT/.spec-eng/gaps.json`.
- The intermediate representation uses JSON.
- Generated tests live in `$PROJECT/.spec-eng/generated/`.
- All file paths in scenarios are relative to `$PROJECT`.

---

## 1. Project Initialization

;===============================================================
; A new project can be initialized for spec engineering.
;===============================================================
GIVEN a directory with no spec engineering configuration.

WHEN the user runs `spec-eng init`.

THEN a `.spec-eng/` directory is created.
THEN a `.spec-eng/config.json` file exists with default settings.
THEN a `specs/` directory is created.
THEN the user sees a message confirming initialization.


;===============================================================
; Initialization detects existing project language and framework.
;===============================================================
GIVEN a directory containing a Python project with pytest.

WHEN the user runs `spec-eng init`.

THEN the config detects language as "python".
THEN the config detects test framework as "pytest".
THEN the user is prompted to confirm or override the detected settings.


;===============================================================
; Initialization detects multiple languages.
;===============================================================
GIVEN a directory containing both TypeScript and Rust source files.

WHEN the user runs `spec-eng init`.

THEN the config lists both detected languages.
THEN the user is prompted to select a primary language or configure both.


;===============================================================
; Re-initialization does not destroy existing specs.
;===============================================================
GIVEN a project already initialized with 5 GWT spec files.

WHEN the user runs `spec-eng init`.

THEN the existing spec files are preserved.
THEN the configuration is updated without data loss.
THEN the user sees a warning that the project was already initialized.


---

## 2. GWT Spec Authoring

;===============================================================
; A new spec file can be created from a description.
;===============================================================
GIVEN an initialized project.

WHEN the user runs `spec-eng new "User Registration"`.

THEN a file `specs/user-registration.gwt` is created.
THEN the file contains a header comment with the description.
THEN the file contains a template GIVEN/WHEN/THEN scaffold.


;===============================================================
; Specs can be authored with AI assistance.
;===============================================================
GIVEN an initialized project.

WHEN the user runs `spec-eng draft "users can register, log in, and reset passwords"`.

THEN the tool produces a draft GWT spec covering registration.
THEN the tool produces a draft GWT spec covering login.
THEN the tool produces a draft GWT spec covering password reset.
THEN each draft is presented for human review before saving.
THEN no draft is saved without explicit user approval.


;===============================================================
; GWT files follow the required format.
;===============================================================
GIVEN a spec file with the content:
  ```
  ;===============================================================
  ; User can register with email and password.
  ;===============================================================
  GIVEN no registered users.

  WHEN a user registers with email "bob@example.com" and password "secret123".

  THEN there is 1 registered user.
  THEN the user "bob@example.com" can log in.
  ```

WHEN the tool parses this file.

THEN 1 scenario is extracted.
THEN the scenario has 1 GIVEN clause.
THEN the scenario has 1 WHEN clause.
THEN the scenario has 2 THEN clauses.
THEN the scenario title is "User can register with email and password."


;===============================================================
; Multiple scenarios in one file are parsed independently.
;===============================================================
GIVEN a spec file with 3 scenarios separated by header comments.

WHEN the tool parses this file.

THEN 3 independent scenarios are extracted.
THEN each scenario has its own title from its header comment.


;===============================================================
; Spec files can reference other spec files for shared state.
;===============================================================
GIVEN a spec file `specs/registration.gwt` that establishes registered users.
GIVEN a spec file `specs/login.gwt` that references "a registered user".

WHEN the tool parses both files.

THEN the tool recognizes that login scenarios depend on registration state.
THEN the dependency is recorded in the state machine graph.


;===============================================================
; Invalid GWT syntax is rejected with a helpful error.
;===============================================================
GIVEN a spec file missing a WHEN clause.

WHEN the tool parses this file.

THEN parsing fails with an error identifying the file and line number.
THEN the error message explains that every scenario requires GIVEN, WHEN, and THEN.


---

## 3. Spec Guardian

;===============================================================
; The guardian detects class/module names in specs.
;===============================================================
GIVEN a spec containing "GIVEN the UserService has no users".

WHEN the guardian analyzes this spec.

THEN a warning is raised for "UserService" as an implementation detail.
THEN a behavioral alternative is suggested: "GIVEN no registered users".
THEN the original spec is not modified.


;===============================================================
; The guardian detects database terminology.
;===============================================================
GIVEN a spec containing "THEN the users table contains 1 row".

WHEN the guardian analyzes this spec.

THEN a warning is raised for "users table" and "row" as implementation details.
THEN a behavioral alternative is suggested: "THEN there is 1 registered user".


;===============================================================
; The guardian detects API/protocol terminology.
;===============================================================
GIVEN a spec containing "WHEN a POST request is sent to /api/users".

WHEN the guardian analyzes this spec.

THEN a warning is raised for "POST request" and "/api/users" as implementation details.
THEN a behavioral alternative is suggested: "WHEN a user registers".


;===============================================================
; The guardian detects framework-specific terminology.
;===============================================================
GIVEN a spec containing "GIVEN the Redis cache is empty".

WHEN the guardian analyzes this spec.

THEN a warning is raised for "Redis cache" as an implementation detail.
THEN a behavioral alternative is suggested: "GIVEN no cached sessions".


;===============================================================
; The guardian accepts pure behavioral language.
;===============================================================
GIVEN a spec containing only behavioral language:
  ```
  GIVEN no registered users.
  WHEN a user registers with email "bob@example.com" and password "secret123".
  THEN there is 1 registered user.
  ```

WHEN the guardian analyzes this spec.

THEN no warnings are raised.


;===============================================================
; The guardian runs automatically on spec save.
;===============================================================
GIVEN an initialized project with the guardian enabled.

WHEN a spec file is saved.

THEN the guardian analyzes the saved file within 2 seconds.
THEN any warnings are displayed to the user.


;===============================================================
; The guardian can be configured with project-specific allowlists.
;===============================================================
GIVEN a project where "API key" is a domain concept, not an implementation detail.

WHEN the user adds "API key" to the guardian allowlist in config.

THEN specs containing "API key" do not trigger warnings.


;===============================================================
; Guardian suggestions require human approval.
;===============================================================
GIVEN the guardian has flagged 3 implementation details in a spec.

WHEN the user reviews the suggestions.

THEN the user can accept, reject, or modify each suggestion individually.
THEN only accepted suggestions are applied to the spec file.
THEN rejected suggestions are recorded so they are not re-raised.


---

## 4. State Machine Extraction

;===============================================================
; A state machine graph is built from a single spec file.
;===============================================================
GIVEN a spec file with 1 scenario:
  GIVEN no registered users.
  WHEN a user registers.
  THEN there is 1 registered user.

WHEN the user runs `spec-eng graph`.

THEN the graph contains 2 states: "no registered users" and "1 registered user".
THEN the graph contains 1 transition: "a user registers".
THEN the transition goes from "no registered users" to "1 registered user".


;===============================================================
; The graph aggregates scenarios across multiple spec files.
;===============================================================
GIVEN 3 spec files with a total of 10 scenarios.

WHEN the user runs `spec-eng graph`.

THEN all 10 scenarios contribute to a single unified graph.
THEN states that appear in multiple files are merged by semantic equivalence.


;===============================================================
; THEN clauses that match GIVEN clauses in other scenarios create edges.
;===============================================================
GIVEN scenario A: GIVEN no users. WHEN user registers. THEN there is 1 user.
GIVEN scenario B: GIVEN there is 1 user. WHEN user logs in. THEN user is logged in.

WHEN the user runs `spec-eng graph`.

THEN the graph connects scenario A's THEN to scenario B's GIVEN.
THEN the full path is: no users → registers → 1 user → logs in → logged in.


;===============================================================
; Semantic equivalence handles minor phrasing differences.
;===============================================================
GIVEN scenario A has THEN: "there is 1 registered user".
GIVEN scenario B has GIVEN: "1 user is registered".

WHEN the user runs `spec-eng graph`.

THEN the tool identifies these as semantically equivalent states.
THEN the user is prompted to confirm or reject the equivalence.
THEN confirmed equivalences are persisted in `.spec-eng/equivalences.json`.


;===============================================================
; The graph identifies entry points.
;===============================================================
GIVEN 5 scenarios where 2 have GIVEN clauses that are not THEN clauses of any other scenario.

WHEN the user runs `spec-eng graph`.

THEN those 2 states are marked as entry points in the graph.


;===============================================================
; The graph identifies terminal states.
;===============================================================
GIVEN 5 scenarios where 1 has a THEN clause that is not a GIVEN clause of any other scenario
  and has no outbound transitions.

WHEN the user runs `spec-eng graph`.

THEN that state is marked as a terminal state in the graph.


;===============================================================
; The graph can be exported as a visual diagram.
;===============================================================
GIVEN a graph has been built with 8 states and 12 transitions.

WHEN the user runs `spec-eng graph --format dot`.

THEN a Graphviz DOT file is produced.
THEN the DOT file contains all 8 states as nodes.
THEN the DOT file contains all 12 transitions as labeled edges.
THEN entry points are visually distinguished.
THEN terminal states are visually distinguished.


;===============================================================
; The graph can be exported as JSON.
;===============================================================
GIVEN a graph has been built.

WHEN the user runs `spec-eng graph --format json`.

THEN a JSON file is produced with states, transitions, entry points, and terminal states.
THEN each state includes a reference to the source spec file and line number.
THEN each transition includes a reference to the source scenario.


;===============================================================
; The graph updates incrementally when specs change.
;===============================================================
GIVEN a graph has been built from 10 scenarios.
GIVEN 1 spec file is modified to add 2 new scenarios.

WHEN the user runs `spec-eng graph`.

THEN only the modified file is re-parsed.
THEN the graph is updated to include the 2 new scenarios.
THEN existing graph data from unmodified files is preserved.


---

## 5. Gap Analysis

;===============================================================
; Dead-end states are identified.
;===============================================================
GIVEN a graph where state "user is locked out" has no outbound transitions.

WHEN the user runs `spec-eng gaps`.

THEN the gap report includes "user is locked out" as a dead-end state.
THEN the report asks: "Is this an intentional terminal state?"


;===============================================================
; Unreachable states are identified.
;===============================================================
GIVEN a graph where state "admin mode active" has no inbound transitions from any entry point.

WHEN the user runs `spec-eng gaps`.

THEN the gap report includes "admin mode active" as unreachable.
THEN the report asks: "How does the system reach this state?"


;===============================================================
; Missing error transitions are identified.
;===============================================================
GIVEN a graph where state "user is logged in" handles "logs out" and "views profile"
  but has no transition for "enters invalid data".

WHEN the user runs `spec-eng gaps`.

THEN the gap report notes that "user is logged in" has no error transition.
THEN the report suggests: "What happens when a logged-in user encounters an error?"


;===============================================================
; Contradictory postconditions are identified.
;===============================================================
GIVEN scenario A: GIVEN 1 user. WHEN user registers. THEN there are 2 users.
GIVEN scenario B: GIVEN 1 user. WHEN user registers. THEN registration fails.

WHEN the user runs `spec-eng gaps`.

THEN the gap report flags a contradiction.
THEN the report shows both scenarios side by side.
THEN the report asks: "These scenarios have the same precondition and event but different outcomes. Is there a missing condition?"


;===============================================================
; Missing negative scenarios are suggested.
;===============================================================
GIVEN specs only describe successful registration.

WHEN the user runs `spec-eng gaps`.

THEN the gap report suggests negative scenarios:
  "What happens when a user registers with an already-taken email?"
  "What happens when a user registers with an invalid password?"
  "What happens when a user registers with a malformed email?"


;===============================================================
; Gap analysis produces a structured report.
;===============================================================
GIVEN a graph with gaps.

WHEN the user runs `spec-eng gaps`.

THEN the report is saved to `.spec-eng/gaps.json`.
THEN each gap has a type (dead-end, unreachable, missing-error, contradiction, missing-negative).
THEN each gap has a severity (high, medium, low).
THEN each gap references the specific states and transitions involved.
THEN each gap includes a suggested question or action.


;===============================================================
; Gaps can be triaged by the user.
;===============================================================
GIVEN a gap report with 5 gaps.

WHEN the user runs `spec-eng triage`.

THEN each gap is presented one at a time.
THEN the user can mark each gap as: "needs spec", "intentional", or "out of scope".
THEN gaps marked "needs spec" generate a GWT template in the appropriate spec file.
THEN gaps marked "intentional" are recorded and not re-raised.
THEN gaps marked "out of scope" are recorded and not re-raised.


;===============================================================
; Resolved gaps reduce the gap count on re-analysis.
;===============================================================
GIVEN a gap report with 5 gaps.
GIVEN the user writes new specs that address 3 of the gaps.

WHEN the user runs `spec-eng gaps`.

THEN the report contains 2 remaining gaps.
THEN the 3 resolved gaps no longer appear.


;===============================================================
; New specs discovered through gap analysis are appended to spec files.
;===============================================================
GIVEN a gap was triaged as "needs spec" for missing error handling on login.

WHEN the user runs `spec-eng triage` and selects "needs spec".

THEN a new scenario template is appended to `specs/login.gwt`.
THEN the template has a GIVEN matching the relevant state.
THEN the template has a WHEN describing the error event.
THEN the template has a placeholder THEN for the user to fill in.
THEN the user is notified that the spec file was updated.


;===============================================================
; Gap analysis can suggest specs using AI assistance.
;===============================================================
GIVEN a gap for a dead-end state "payment failed".

WHEN the user runs `spec-eng gaps --suggest`.

THEN the tool generates candidate GWT scenarios for recovery from "payment failed".
THEN each candidate is presented for human review.
THEN no candidate is added to spec files without explicit approval.


;===============================================================
; Gap analysis runs automatically after graph updates.
;===============================================================
GIVEN an initialized project with auto-analysis enabled.

WHEN the user runs `spec-eng graph`.

THEN gap analysis runs automatically after the graph is built.
THEN new gaps are displayed to the user.
THEN previously triaged gaps are not re-displayed.


---

## 6. Pipeline Bootstrap

;===============================================================
; A parser/generator pipeline is bootstrapped for the detected language.
;===============================================================
GIVEN an initialized project with language "python" and framework "pytest".
GIVEN at least 1 GWT spec file exists.

WHEN the user runs `spec-eng bootstrap`.

THEN a parser is generated that reads `.gwt` files and produces JSON IR.
THEN a generator is generated that reads JSON IR and produces pytest test files.
THEN both are stored in `.spec-eng/pipeline/`.
THEN the user sees a summary of what was generated.


;===============================================================
; The bootstrapped parser correctly parses all existing specs.
;===============================================================
GIVEN a bootstrapped pipeline.
GIVEN 5 existing GWT spec files.

WHEN the user runs `spec-eng parse`.

THEN all 5 files are parsed without errors.
THEN the JSON IR contains all scenarios from all files.
THEN each scenario in the IR includes the source file and line number.


;===============================================================
; The bootstrapped generator produces runnable tests.
;===============================================================
GIVEN a bootstrapped pipeline with parsed IR.

WHEN the user runs `spec-eng generate`.

THEN test files are produced in `.spec-eng/generated/`.
THEN each test file corresponds to a spec file.
THEN the generated tests are syntactically valid for the target framework.


;===============================================================
; The pipeline can be re-bootstrapped when project structure changes.
;===============================================================
GIVEN a bootstrapped pipeline.
GIVEN the project has added new modules or changed its structure.

WHEN the user runs `spec-eng bootstrap --refresh`.

THEN the pipeline is regenerated with awareness of the new structure.
THEN existing spec files are not affected.
THEN previously generated tests are replaced by new generated tests.


;===============================================================
; The pipeline validates itself against a reference spec.
;===============================================================
GIVEN a freshly bootstrapped pipeline.

WHEN the bootstrap completes.

THEN the tool runs the pipeline on a built-in reference spec.
THEN the reference spec parses successfully.
THEN the reference spec generates a test that compiles/loads without errors.
THEN the user sees confirmation that the pipeline is working.


;===============================================================
; The IR is inspectable and human-readable.
;===============================================================
GIVEN a parsed spec.

WHEN the user runs `spec-eng parse --inspect`.

THEN the JSON IR is displayed in a readable format.
THEN each scenario shows its GIVEN, WHEN, and THEN clauses.
THEN metadata (source file, line number, scenario title) is visible.


---

## 7. Test Generation and Execution

;===============================================================
; Generated tests execute and report results.
;===============================================================
GIVEN a bootstrapped pipeline with generated tests.
GIVEN an implementation that satisfies the specs.

WHEN the user runs `spec-eng test`.

THEN the generated acceptance tests are executed.
THEN the results show how many scenarios passed and failed.
THEN failing scenarios reference the source spec file and line number.


;===============================================================
; Generated tests fail when implementation does not satisfy specs.
;===============================================================
GIVEN a bootstrapped pipeline with generated tests.
GIVEN an implementation that does NOT satisfy 2 of the specs.

WHEN the user runs `spec-eng test`.

THEN 2 scenarios are reported as failing.
THEN each failure shows the expected behavior (from the spec) and actual behavior.


;===============================================================
; Tests are regenerated when specs change.
;===============================================================
GIVEN generated tests from a previous run.
GIVEN a spec file has been modified.

WHEN the user runs `spec-eng test`.

THEN the modified spec is re-parsed.
THEN the affected tests are regenerated before execution.
THEN unmodified tests are not regenerated.


;===============================================================
; The user is warned when writing code without specs.
;===============================================================
GIVEN an initialized project with no spec files.

WHEN the user runs `spec-eng test`.

THEN the tool warns that no specs exist.
THEN the tool suggests running `spec-eng new` or `spec-eng draft`.


;===============================================================
; Generated test files are never manually edited.
;===============================================================
GIVEN generated test files in `.spec-eng/generated/`.

WHEN the user modifies a generated test file.
WHEN the user runs `spec-eng test`.

THEN the modified file is overwritten by regeneration.
THEN the user is warned that manual edits to generated files are not preserved.


---

## 8. Dual Test Stream Verification

;===============================================================
; Both acceptance tests and unit tests must pass.
;===============================================================
GIVEN acceptance tests (from specs) that all pass.
GIVEN unit tests (from the project's test suite) where 1 fails.

WHEN the user runs `spec-eng verify`.

THEN verification fails.
THEN the report shows acceptance tests passed but unit tests failed.
THEN the report identifies the failing unit test.


;===============================================================
; Acceptance tests passing with no unit tests triggers a warning.
;===============================================================
GIVEN acceptance tests that all pass.
GIVEN no unit tests exist in the project.

WHEN the user runs `spec-eng verify`.

THEN the tool warns that only one test stream exists.
THEN the tool suggests that unit tests are needed to constrain HOW the implementation works.


;===============================================================
; Verification reports coverage of specs vs implementation.
;===============================================================
GIVEN 10 GWT scenarios generating 10 acceptance tests.
GIVEN 8 of those tests exercise code paths that also have unit tests.
GIVEN 2 acceptance tests exercise code paths with no unit tests.

WHEN the user runs `spec-eng verify`.

THEN the report shows 80% dual-stream coverage.
THEN the report identifies the 2 scenarios lacking unit test coverage.


---

## 9. The Full Workflow

;===============================================================
; The status command shows the current state of the project.
;===============================================================
GIVEN an initialized project with 5 spec files, a built graph, and a gap report.

WHEN the user runs `spec-eng status`.

THEN the output shows: 5 spec files, N scenarios, M states, K transitions.
THEN the output shows: gap report has X unresolved gaps.
THEN the output shows: pipeline status (bootstrapped or not).
THEN the output shows: last test run results (if any).


;===============================================================
; A new user can go from zero to running acceptance tests.
;===============================================================
GIVEN an empty project directory with a Python/pytest project.

WHEN the user runs `spec-eng init`.
WHEN the user runs `spec-eng draft "users can register and log in"`.
WHEN the user approves the drafted specs.
WHEN the user runs `spec-eng graph`.
WHEN the user runs `spec-eng gaps`.
WHEN the user triages any gaps.
WHEN the user runs `spec-eng bootstrap`.
WHEN the user runs `spec-eng test`.

THEN each step completes successfully.
THEN the user has executable acceptance tests derived from behavioral specs.


;===============================================================
; The graph → gaps → spec cycle is iterative.
;===============================================================
GIVEN 5 initial spec files.

WHEN the user runs `spec-eng graph`.
WHEN the user runs `spec-eng gaps`.
WHEN the user writes 3 new specs to address gaps.
WHEN the user runs `spec-eng graph`.
WHEN the user runs `spec-eng gaps`.

THEN the second gap report has fewer gaps than the first.
THEN any new gaps introduced by the 3 new specs are identified.


;===============================================================
; CI integration runs the full verification pipeline.
;===============================================================
GIVEN a project with specs, a bootstrapped pipeline, and generated tests.

WHEN the CI system runs `spec-eng ci`.

THEN specs are parsed.
THEN the graph is built.
THEN gap analysis runs (failing the build if unresolved critical gaps exist).
THEN tests are generated.
THEN acceptance tests are executed.
THEN unit tests are executed.
THEN the build passes only if both test streams pass and no critical gaps exist.


;===============================================================
; The tool can be run in non-interactive mode for CI.
;===============================================================
GIVEN a CI environment with no interactive terminal.

WHEN the tool runs with `--non-interactive` flag.

THEN all prompts use default or configured values.
THEN no user input is required.
THEN all output goes to stdout/stderr.
THEN exit codes indicate success (0) or failure (non-zero).


---

## 10. Spec Portability

;===============================================================
; The same spec files work across different language targets.
;===============================================================
GIVEN a project with GWT spec files.
GIVEN the pipeline is bootstrapped for Python/pytest.
GIVEN a second pipeline is bootstrapped for TypeScript/Jest.

WHEN the user runs `spec-eng test --target python`.
WHEN the user runs `spec-eng test --target typescript`.

THEN both targets execute tests derived from the same spec files.
THEN both targets report results against the same scenarios.


;===============================================================
; Spec files contain no language-specific constructs.
;===============================================================
GIVEN a spec file authored for a Python project.

WHEN the same spec file is used in a Rust project.

THEN the spec file parses without modification.
THEN the generator produces Rust-appropriate tests.


---

## 11. Configuration and Customization

;===============================================================
; The guardian sensitivity can be adjusted.
;===============================================================
GIVEN a project where some technical terms are domain language.

WHEN the user configures guardian sensitivity to "low".

THEN only high-confidence implementation details are flagged.
THEN domain-specific technical terms are not flagged.


;===============================================================
; Custom GWT vocabulary can be defined per project.
;===============================================================
GIVEN a game project that uses "player", "turn", "board" as domain terms.

WHEN the user adds these to the project vocabulary in config.

THEN the parser understands these terms in GIVEN/WHEN/THEN clauses.
THEN the guardian does not flag these as implementation details.


;===============================================================
; The tool respects .gitignore patterns.
;===============================================================
GIVEN a project with a `.gitignore` that excludes `.spec-eng/generated/`.

WHEN the user runs `spec-eng generate`.

THEN generated files are created in `.spec-eng/generated/`.
THEN the tool does not modify `.gitignore`.
THEN the user is informed that generated files should be gitignored.


---

## 12. Error Handling and Edge Cases

;===============================================================
; Empty spec files are handled gracefully.
;===============================================================
GIVEN a spec file that exists but contains no scenarios.

WHEN the tool parses this file.

THEN no scenarios are extracted.
THEN no error is raised.
THEN the file is listed as "empty" in status output.


;===============================================================
; Circular state references are detected.
;===============================================================
GIVEN scenario A: GIVEN state X. WHEN event 1. THEN state Y.
GIVEN scenario B: GIVEN state Y. WHEN event 2. THEN state X.

WHEN the user runs `spec-eng graph`.

THEN the graph correctly represents the cycle.
THEN the cycle is noted in the graph metadata.
THEN gap analysis does not flag cycles as errors (they may be intentional).


;===============================================================
; Very large spec suites are handled without degradation.
;===============================================================
GIVEN a project with 100 spec files containing 500 scenarios.

WHEN the user runs `spec-eng graph`.

THEN the graph is built within 30 seconds.
THEN the graph is correct and complete.


;===============================================================
; The tool works without an internet connection.
;===============================================================
GIVEN no internet connectivity.
GIVEN a bootstrapped pipeline with existing specs.

WHEN the user runs `spec-eng parse`.
WHEN the user runs `spec-eng graph`.
WHEN the user runs `spec-eng gaps`.
WHEN the user runs `spec-eng test`.

THEN all commands succeed.
THEN AI-assisted features (draft, suggest) are unavailable with a clear message.
THEN deterministic features (parse, graph, gaps, test) work fully offline.


;===============================================================
; Conflicting spec files are reported.
;===============================================================
GIVEN two spec files that define the same scenario title with different content.

WHEN the user runs `spec-eng parse`.

THEN a warning is raised about the duplicate scenario title.
THEN both scenarios are parsed but flagged as potentially conflicting.


---

## Meta: Self-Verification

This specification is itself subject to gap analysis. The state machine of the
`spec-eng` tool, as described by these scenarios, should be extracted and analyzed
for completeness.

;===============================================================
; This spec document can be analyzed by the tool it specifies.
;===============================================================
GIVEN this SPEC.md file.

WHEN the user runs `spec-eng graph --file SPEC.md`.

THEN the tool extracts all scenarios from this document.
THEN a state machine of the spec-eng tool itself is produced.
THEN gap analysis identifies any missing states or transitions in this specification.

;===============================================================
; Gaps found in this spec are addressed by appending new scenarios.
;===============================================================
GIVEN gap analysis reveals a missing state in this specification.

WHEN the user writes a new scenario to cover that gap.

THEN the scenario is appended to the appropriate section of this document.
THEN the graph is rebuilt to include the new scenario.
THEN the gap count decreases.


---

## Appendix: Scenario Index

Total scenarios: 52

| Section | Count |
|---------|-------|
| 1. Project Initialization | 4 |
| 2. GWT Spec Authoring | 6 |
| 3. Spec Guardian | 8 |
| 4. State Machine Extraction | 9 |
| 5. Gap Analysis | 10 |
| 6. Pipeline Bootstrap | 6 |
| 7. Test Generation and Execution | 5 |
| 8. Dual Test Stream Verification | 3 |
| 9. The Full Workflow | 4 |
| 10. Spec Portability | 2 |
| 11. Configuration and Customization | 3 |
| 12. Error Handling and Edge Cases | 5 |
| Meta: Self-Verification | 2 |

This index is updated when scenarios are added or deprecated.
