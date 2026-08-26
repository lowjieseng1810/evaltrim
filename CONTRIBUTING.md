# Contributing

EvalTrim is a CLI for evidence-backed eval-suite maintenance.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

## Checks (release gates)

```bash
python3 -m pytest
python3 -m ruff check src tests
python3 -m ruff format --check src tests
python3 -m mypy src/evaltrim
python3 -m build
scripts/demo.sh
```

## Guidelines

- Do not auto-delete or auto-edit user suites.
- Defaults must work offline.
- Unique critical witnesses must never `RETIRE`.
- Do not add hosted SaaS, IDE, or a full MCP platform in this tree.
- Do not lower the global merge threshold to chase recall.
- Do not rename the public brand without a documented naming audit (`docs/naming-audit.md`).

Public demo: `scripts/demo-public.sh`. Screenshots: `python3 scripts/generate_demo_screenshots.py`.
