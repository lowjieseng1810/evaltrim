# Removal simulation

This is the proof mechanism. EvalTrim never deletes files.

Given a candidate id:

1. Compute baseline behavior coverage and critical coverage.
2. Drop that test using a precomputed holder index (O(unique atoms), not a full coverage rebuild per candidate).
3. Recompute coverage, unique witnesses, and lost atoms.
4. Emit a `RemovalSimulation` with a verdict.

## Verdicts

- `SAFE_TO_RETIRE` — no lost behavior atoms and no critical coverage drop.
- `KEEP` — the case uniquely protects behavior, a critical requirement, or critical coverage.
- `REVIEW` — coverage drop exceeds policy, or historical failures exist.
- `UNCERTAIN` — low-confidence heuristic behavior signature.

JSON `evidence` records unique witnesses lost, critical/requirement coverage lost, historical failure contribution, and counterfactual coverage loss.

## CLI

```bash
evaltrim simulate-remove evals.yaml refund-001
evaltrim simulate-remove evals.yaml refund-001 --format json
```

Interpret `SAFE_TO_RETIRE` as “coverage math does not object.” Maintainers still review wording, product intent, and any external SLAs.
