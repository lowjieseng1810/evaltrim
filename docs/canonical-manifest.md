# Canonical evaluation manifest

Internal type: `evaltrim.core.manifest.EvaluationRecord`.

It is vendor-neutral. YAML suites, JSONL rows, and future Promptfoo-like files should map *into* this record, not the other way around.

## Fields

| Field | Meaning |
| --- | --- |
| `id`, `version` | Stable identity |
| `agent` | Optional agent name |
| `input`, `messages` | Prompt / conversation |
| `expected` | Oracle text (optional) |
| `requirements` | Requirement ids |
| `behavior` | EvalTrim behavior signature |
| `critical` | Criticality flag |
| `graders` | List of `{type, params, weight}` |
| `output` | `AgentOutput` after a run |
| `grades` | `GradeResult` list |
| `provenance` | source, model, provider, recording id |
| `lifecycle` | DRAFT…ARCHIVED (string) |
| `usage` on output | latency, tokens, cost |

`TestCase.from` mapping: `EvaluationRecord.from_test_case(test)`.

Export/import today: EvalTrim YAML/JSON, JSONL. Other vendors are adapter work for later phases.
