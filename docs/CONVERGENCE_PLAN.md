# Convergence Plan

## Date Context
- Today: Wednesday, February 18, 2026.
- Target checkpoint: Sunday, February 22, 2026.

## Goal
Increase repo-level GWT/DAL convergence by iteratively expanding vocabulary, reducing false-positive lints, and re-evaluating generated specs against documented repo behavior.

## Execution Loop
1. Run batch evaluator across selected repos.
2. Rank failures and low-alignment repos.
3. Extract missing domain concepts and add vocab entries.
4. Re-run evaluation on the same repo set.
5. Track trends (alignment, failures, iterations-to-approval).

## Automation Implemented
- `scripts/repo_convergence_eval.py`
  - Pulls repos from GitHub API
  - Runs interrogation loop in parallel (`--workers`)
  - Produces JSON + Markdown reports in `reports/`
- HTTP + MCP + CLI paths are already available for deeper integration.

## Candidate Parallelization
- Local thread parallelization is already in the evaluator.
- External agent fanout (e.g., coding-agent-bridge subscriptions) can assign repo subsets to independent workers and merge reports.

## Near-Term Target (before Sunday)
- Evaluate 50 repos/tasks total (including repeated re-runs after vocab updates).
- Reduce failed runs to near-zero.
- Improve average alignment recall trend line over at least 3 passes.
