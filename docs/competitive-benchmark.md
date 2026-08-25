# Competitive benchmark

This is a **verification** suite, not a feature catalog. It does not inflate EvalTrim by counting unmeasured competitor cells as wins.

## Run

```bash
evaltrim benchmark competitive --format json
evaltrim benchmark competitive --competitor agenteval --format json
evaltrim benchmark competitive --scale 100,500,1000,5000,10000 --write-docs
```

Tasks `01`–`20` live in `benchmarks/competitive/tasks/`. Methodology is in `docs/competitive-methodology.md`. Environment lock is `benchmarks/competitive/environment.yaml`.

## Rules

- Measure EvalTrim in this repository.
- Do not invent competitor numbers.
- **UNMEASURED** is not a win.
- Hosted observability (Langfuse, Phoenix, Braintrust) is **NOT DIRECTLY COMPARABLE** unless a capability is reproduced locally.

## Sources (2026-08-25)

- AgentEval GitHub README: 11 graders including trajectory
- AgentEval PyPI 0.7.0 wheel: 10 graders, no trajectory module
- Promptfoo red-team plugins docs: 157 documented (catalog breadth, not CLI-counted)
- DeepEval / Inspect AI / EvalView: not executed in this environment
