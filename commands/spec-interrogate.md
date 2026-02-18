# /spec-interrogate — Run Interrogation Loop

Run one deterministic interrogation iteration that updates GWT, compiles DAL/IR, and tracks open questions.

## Usage

```
/spec-interrogate <idea> [answers]
```

## CLI Equivalent

```bash
spec-eng interrogate --idea "<idea>" \
  --answer success_criteria="..." \
  --answer failure_case="..." \
  --answer constraints="..."
```

Add `--approve` only after IR is stable and blocking questions are resolved.
