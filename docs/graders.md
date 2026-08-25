# Graders

Registered in `evaltrim.evaluation.graders.REGISTRY` via `register_grader(cls, aliases=...)`.

Built-ins are deterministic (except `llm_judge`, which skips until a callable is configured) and JSON-serializable as `GraderSpec`.

| Type | Local? | Notes |
| --- | --- | --- |
| `exact` | yes | Strip equality |
| `contains` / `not_contains` | yes | |
| `regex` | yes | Invalid patterns fail closed |
| `json` / `json_schema` | yes | `json.loads` plus a JSON Schema *subset* (`type`, `required`, `properties`, `enum`, `items`) |
| `json_path` | yes | `$.a.b[0]` plus `equals` / `exists` |
| `semantic` | yes | Two-document local cosine; optional encoder is separate |
| `numeric_tolerance` / `numeric` | yes | Absolute / relative tolerance |
| `set_equality` / `list_equality` | yes | Order-insensitive |
| `llm_judge` | skip | Interface only until `params.callable` is set |
| `custom` | caller | `module:function` |
| `tool_call` / `tool_args` | yes | Names and argument constraints |
| `required_tool` / `forbidden_tool` | yes | Aliases `required_action` / `forbidden_action` |
| `max_tool_calls` / `max_trajectory_length` | yes | |
| `trajectory` | yes | `mode`: subsequence (default), `lcs`, `strict` |
| `lcs_trajectory` / `strict_trajectory` / `ordered_subsequence` | yes | |
| `state_predicate` | yes | Compare `metadata.state` / last trajectory payload |
| `latency` / `ttft` / `tokens` / `cost` | yes | Skip if the usage field is missing |

Multiple graders on one record are AND-composed (`overall_pass`).

## Write a plugin

```python
from evaltrim.core.manifest import GradeResult
from evaltrim.evaluation.graders import Grader, register_grader

class AlwaysPass(Grader):
    name = "always_pass"

    def grade(self, record, output, spec):
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="plugin")

register_grader(AlwaysPass)
```

YAML:

```yaml
graders:
  - type: always_pass
```

Statistics (`mean`, `median`, sample `variance`, Wald CI, Welch, bootstrap) assume i.i.d. numeric samples. They are **descriptive**, not a substitute for experiment design.
