# Architecture

EvalTrim v0.2 is a **local evaluation control plane**. This document is both an assessment of v0.1 and the Phase A layout.

## v0.1 assessment (preserved)

The v0.1 CLI remains the intelligence layer:

```
suite.yaml/json
  → parser (Pydantic)
  → behavior signatures
  → candidate pairs (full pairwise ≤200 tests; blocking above)
  → multi-factor similarity
  → unique witnesses + boundary marks
  → in-memory removal simulation
  → KEEP / MERGE / RETIRE / REVIEW
  → markdown / JSON / GitHub comment
```

Preserved commands: `analyze`, `simulate-remove`, `maintain`, `benchmark`, `validate`, `init`, `report`.

## Phase A boundaries (v0.2)

New packages sit *beside* the v0.1 modules. Nothing was rewritten “for style.”

| Package | Role |
| --- | --- |
| `evaltrim.core` | Canonical `EvaluationRecord` manifest; re-exports policies/models |
| `evaltrim.evaluation` | Graders, assertions, multi-run statistics |
| `evaltrim.runtime` | Local adapters, batch runner, record/replay |
| `evaltrim.regression` | Snapshot save/load and **suite** diffs (not live-agent claims) |
| `evaltrim.integrations` | JSONL importer |
| `evaltrim.embeddings` | Optional hashing encoder; off by default |
| `evaltrim.policy` | `evaltrim.yaml` policy-as-code |

Future phases (trace watch, MCP, sandbox backends, portfolio optimizer) get folders later. Do not treat empty folders as features.

## Data flow (Phase A)

```
TestSuite ──► EvaluationRecord ──► AgentAdapter.run ──► AgentOutput
                     │                                         │
                     └── graders / assertions ◄────────────────┘
                     │
                     └── analyze_suite (portfolio intelligence)
```

## Design rules

- No hosted backend, no telemetry, no default network.
- Recommendations never delete files.
- Snapshot compare language is about **suites**, not production agent regressions.
- LLM judge grader is an interface; default result is `skipped`.
