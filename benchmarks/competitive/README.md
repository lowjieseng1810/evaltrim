# Competitive harness

Common tasks live in `tasks/`. Shared grader gold cases live in `fixtures/`.
Version lock is `environment.yaml`.

```bash
PYTHONPATH=src python3 -m evaltrim.cli benchmark competitive --format json
PYTHONPATH=src python3 -m evaltrim.cli benchmark competitive --competitor agenteval
PYTHONPATH=src python3 -m evaltrim.cli competitive-benchmark --format json
```

Do not paste guessed competitor timings. UNMEASURED is not a win.
