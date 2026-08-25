# Removal simulation

This is the proof mechanism. EvalTrim never deletes files.

Given a candidate id:

1. Compute baseline behavior coverage and critical coverage.
2. Drop that test from an in-memory copy.
3. Recompute coverage, unique witnesses, and lost atoms.
4. Emit a `RemovalSimulation` with a verdict.

## Verdicts

- `SAFE_TO_RETIRE` — no lost behavior atoms and no critical coverage drop.
- `KEEP` — the case uniquely protects behavior, especially critical behavior.
- `REVIEW` is reserved for recommendation policy when oracles conflict; simulation itself is KEEP vs SAFE_TO_RETIRE.

## CLI

```bash
evaltrim simulate-remove evals.yaml refund-001
evaltrim simulate-remove evals.yaml refund-001 --format json
```

Interpret `SAFE_TO_RETIRE` as “coverage math does not object.” Maintainers still review wording, product intent, and any external SLAs.
