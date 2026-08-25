# Architecture

EvalTrim is a local CLI. Analysis is a pure function from a suite file to a report.

```
suite.yaml/json
    -> parser (Pydantic)
    -> behavior signatures (tags, else heuristics, else optional LLM)
    -> similarity matrix (TF-IDF + Jaccard + run-stats)
    -> unique witnesses
    -> removal simulation (in memory)
    -> recommendations (KEEP / MERGE / RETIRE / REVIEW)
    -> markdown / JSON / GitHub comment
```

## Package layout

- `evaltrim.models` — canonical types. Importers should map into `TestCase` / `TestSuite`.
- `evaltrim.parser` — YAML and JSON loaders.
- `evaltrim.behavior` — deterministic signature extraction.
- `evaltrim.similarity` — multi-factor pair scores.
- `evaltrim.coverage` — atom coverage and uniqueness.
- `evaltrim.simulate` — virtual removal.
- `evaltrim.recommend` — explainable policy.
- `evaltrim.analyze` — pipeline.
- `evaltrim.reports` — rendering.
- `evaltrim.cli` — Typer commands.
- `evaltrim.llm` — optional interfaces; unused unless the user wires a provider.

There is no hosted service, no database server, and no required SQLite. All structures are in-memory.

## Design rule

Recommendations are evidence. The tool never deletes or rewrites the suite.
