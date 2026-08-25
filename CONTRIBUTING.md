# Contributing

EvalTrim is a CLI for evidence-backed eval-suite maintenance. Changes should serve that job: coverage mapping, redundancy, unique witnesses, removal simulation, and reports.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Checks

```bash
ruff check src tests
pytest
evaltrim analyze examples/demo_suite.yaml
```

## Guidelines

- Type-annotate public functions.
- Do not add a hosted service, dashboard, or telemetry.
- Do not auto-delete or auto-edit user suites.
- Keep LLM code behind `evaltrim.llm` interfaces; defaults must work offline.
- Prefer tests that lock recommendation policy (especially: never `RETIRE` a unique critical witness).
