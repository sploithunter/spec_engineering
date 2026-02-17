# /spec-gaps — Run Gap Analysis

Analyze GWT specs for completeness gaps in the state machine.

## What this does

1. Parses all `specs/*.gwt` files
2. Builds the state machine graph
3. Runs five gap analysis checks:
   - **Dead ends** (MEDIUM): States with no outbound transitions
   - **Unreachable states** (HIGH): States with no path from entry points
   - **Missing error paths** (LOW): States handling events but no error transitions
   - **Contradictions** (HIGH): Same precondition + event leading to different outcomes
   - **Missing negatives** (MEDIUM): States with only positive scenarios
4. Presents findings with questions to guide spec improvement

## Usage

```
/spec-gaps [file.gwt]
```

Without arguments, analyzes all specs. With a file argument, analyzes only that file.

## MCP Tools Used

- `mcp__spec-eng__analyze_spec_gaps` — run the gap analysis engine
- `mcp__spec-eng__build_state_graph` — for context on the graph structure

## Output

Gaps grouped by severity (HIGH first), each with:
- Gap type and severity
- Description of the issue
- Guiding question to resolve the gap
- Affected states and transitions

Previously triaged gaps (marked as "intentional" or "out-of-scope") are excluded.
