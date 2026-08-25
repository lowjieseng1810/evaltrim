# Competitive harness

Inputs live in this directory. The runner is `python -m evaltrim.cli competitive-benchmark`.

It measures **EvalTrim** on this machine. Competitor cells are `UNMEASURED` unless you add a reproduced result file.

Do not paste guessed competitor timings.

```bash
PYTHONPATH=src python3 -m evaltrim.cli competitive-benchmark --format json
```

See `docs/competitive-results.md` after a run.
