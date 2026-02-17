# /spec-graph — Build and Display State Machine Graph

Build a state machine graph from GWT specs and display the results.

## What this does

1. Parses all `specs/*.gwt` files using the recursive descent parser
2. Extracts states (from GIVEN/THEN clauses) and transitions (from WHEN clauses)
3. Identifies entry points, terminal states, and cycles
4. Detects semantically equivalent state labels
5. Displays the graph structure

## Usage

```
/spec-graph [--format dot|json] [file.gwt]
```

- Without arguments: processes all specs, displays summary
- With `--format dot`: outputs Graphviz DOT for visualization
- With `--format json`: outputs machine-readable JSON
- With a file argument: processes only that file

## MCP Tools Used

- `mcp__spec-eng__build_state_graph` — extract the state machine
- `mcp__spec-eng__find_equivalences` — detect duplicate state labels
- `mcp__spec-eng__export_graph` — export as DOT or JSON

## Output

- State count and list
- Transition count and list
- Entry points (states that are only preconditions)
- Terminal states (states that are only postconditions)
- Cycles (feedback loops in the state machine)
- Semantic equivalences (potential duplicate state labels)
