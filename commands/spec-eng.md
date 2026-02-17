# /spec-eng — Start Full ATDD Workflow

Start the spec-eng Acceptance Test-Driven Development workflow for a feature.

## What this does

Invokes the `spec-eng` skill which walks through the full 8-step ATDD process:

1. Understand the feature (clarifying questions)
2. Write GWT specs (behavioral specifications in domain language)
3. Parse and validate specs
4. Build state machine graph
5. Run gap analysis
6. Generate complete, runnable acceptance tests
7. Implement with TDD (red-green-refactor)
8. Review specs for implementation leakage

## Usage

```
/spec-eng [feature description]
```

If no description is provided, you'll be asked to describe the feature.

## Example

```
/spec-eng user authentication with email and password
```

This will guide you through writing behavioral specs, validating them with the parser and graph builder, generating real test code, and implementing the feature test-first.
