# /spec-check — Audit Specs for Implementation Leakage

Run the spec guardian to check all `.gwt` files for implementation detail leakage.

## What this does

Invokes the `spec-guardian` agent which:

1. Runs deterministic regex patterns against all specs (fast pass)
2. Performs AI review for subtler leakage (deep pass)
3. Reports findings with suggested behavioral rewrites
4. Gives a pass/fail verdict

## Usage

```
/spec-check [file.gwt]
```

Without arguments, checks all `specs/*.gwt` files. With a file argument, checks only that file.

## Output

For each finding:
- File and line number
- Original clause text
- What was detected (category: class_name, database, api, framework)
- Suggested behavioral rewrite

Summary includes pass/fail verdict and stats by category.
