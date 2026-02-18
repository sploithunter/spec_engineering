# /spec-compile — Normalize Dual-Spec Artifacts

Compile GWT/DAL into synchronized DAL, canonical GWT, IR JSON, and roundtrip diff.

## Usage

```
/spec-compile <spec-file>
```

## CLI Equivalent

```bash
spec-eng spec-compile --in specs/<slug>.txt
spec-eng spec-compile --in specs/<slug>.dal
```

Run repeatedly until outputs stabilize (no artifact changes) and IR equivalence gates pass.
