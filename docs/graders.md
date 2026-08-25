# Graders

Registered in `evaltrim.evaluation.graders.REGISTRY`.

| Type | Local? | Notes |
| --- | --- | --- |
| `exact` | yes | Strip equality |
| `contains` | yes | Default when a suite test has `expected` |
| `regex` | yes | |
| `json` | yes | `json.loads` + optional `required` keys (not full JSON Schema) |
| `semantic` | yes | Two-document TF-IDF cosine; threshold param |
| `llm_judge` | skip | Interface only until a provider is wired |
| `tool_call` | yes | required / forbidden tool names |
| `trajectory` | yes | `max_steps`, `order` |
| `latency` | yes | skipped if unused |
| `cost` | yes | skipped if unused |

Custom graders: implement `Grader` and add to `REGISTRY` in-process. No plugin discovery in v0.2.

Statistics (`mean`, `median`, sample `variance`, Wald CI) assume i.i.d. numeric samples. They are **descriptive**, not a substitute for experiment design.
