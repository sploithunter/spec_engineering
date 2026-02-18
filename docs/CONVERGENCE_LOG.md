# Convergence Log

## 2026-02-18
- Added standalone convergence evaluator script: `scripts/repo_convergence_eval.py`.
- Confirmed interrogation-loop execution on selected `sploithunter` repos.
- Observed low alignment recall baseline with generic interrogation language.
- Identified key improvement levers:
  - domain vocab coverage,
  - false-positive lint tuning (e.g., token suffix collisions),
  - repo-specific expectation templates.

### Next Actions
1. Run evaluator with `--limit 20`, then `--limit 27` for full current owner set.
2. Patch vocab for top mismatch clusters.
3. Re-run and compare report deltas.

## 2026-02-18 (Batch Pass 1)
- Ran: `scripts/repo_convergence_eval.py --owner sploithunter --limit 27 --workers 8`
- Reports:
  - `reports/convergence_sploithunter_20260218T042448Z.json`
  - `reports/convergence_sploithunter_20260218T042448Z.md`
- Summary:
  - Total repos evaluated: 25
  - Successful approvals: 24
  - Failed: 1 (`feedback-system-template`)
  - Average alignment recall: 0.057

### Failure Notes
- `feedback-system-template` failed approval due to unresolved blocking questions.
- This indicates the generic auto-answer set is insufficient for at least one repo profile and needs repo-specific answer templates.

### Automation Opportunities Identified
1. Repo-type classifier -> choose tailored answer templates before interrogation.
2. Retry strategy for unresolved blocking questions with follow-up generated answers.
3. Domain vocab bootstrap from README noun phrases before first interrogation pass.
4. Parallel fanout execution via external coding-agent bridge workers by repo subset.

## 2026-02-18 (100-repo Build + 80/20 Split)
- Built dataset from 100 medium/well-documented repos (GitHub search based).
- Artifacts:
  - `datasets/repo_pairs/` (per-repo GWT/DAL/canonical/IR + metadata)
  - `datasets/repo_pairs_manifest.json`
  - `datasets/repo_pairs_split.json`
- Results:
  - Eligible: 100
  - Stable/approved (`ok`): 68
  - Failed: 32
  - Repo-level split from `ok` set: Train 54 / Eval 14

### Failure Breakdown (first pass)
- `type_validation`: 19
- `spec_check_violation`: 10
- `blocking_questions`: 3

### Interpretation
- Current vocab/type constraints and lint rules are the dominant blockers.
- This confirms that convergence improvements now depend on:
  1) sanitizing/normalizing repo descriptions into allowed vocab types,
  2) tuning overly broad leakage token checks,
  3) strengthening automated answer completion to clear blocking questions.
