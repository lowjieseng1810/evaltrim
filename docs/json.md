# JSON for coding agents

`contract_version`: **1.0**. Field names below are part of the 0.7 contract. Extra keys may appear; do not require unknown keys to be absent.

`--format json` writes UTF-8 JSON to stdout (not wrapped by Rich tables). Many command payloads also include `"command"` and `"contract_version"`.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 2 | missing file, bad YAML/JSON, duplicate IDs, empty suite, unknown test id |
| 3 | `--strict` / policy / gate failure |
| 4 | internal (corrupt store after recovery failed, unexpected) |

## `evaltrim status --format json`

```
project, suite_size, active_tests, recommendations{KEEP,MERGE,RETIRE,REVIEW},
flaky[], stale[], conflicts[], critical_coverage, evaluation_debt, suite_health,
recent_regressions[], note
```

## `evaltrim analyze --format json`

`AnalysisResult` pydantic dump: `summary`, `coverage`, `evidence`, `pairs`, `witnesses`, `recommendations` (each with `evidence` ledger + `proof`), `conflicts`, `timings`, `methodology`, `clusters`, `information_gain`, `failure_values`, `contract_version`.

Recommendation `evidence` ledger:

```
decision, semantic_similarity, behavior_overlap, unique_witnesses_lost,
critical_coverage_lost, requirement_coverage_lost, historical_failure_contribution,
counterfactual_coverage_loss, counterfactual_status, oracle_status, notes,
proof[], information_gain, failure_detection_value
```

## `evaltrim explain ID --suite PATH --format json`

```
id, kind, verdict, unique_witness, critical, other_tests_covering_same_behavior,
removal_simulation, evidence, reasons, flake, summary
```

## `evaltrim impacted-tests SUITE PATHS --format json`

```
{ "tests": [ { test_id, priority, evidence[], note } ], execution { selected, buckets, execution_reduction }, note }
```

`priority`: `CRITICAL` | `DIRECT` | `RISKY` | `ADJACENT` | `LOW_PRIORITY`. Heuristic.
`--safety-sample` keeps a configurable fraction of non-targeted tests.

## `evaltrim gate SUITE --format json`

```
mode, strict, changed_paths, selected_tests, impacted, problems, note
```

Does not run the agent.

## `evaltrim doctor --format json`

```
overall (PASS|WARN|FAIL), checks[{name,status,detail}], network
```

## `evaltrim regression` / `compare-runs`

Recorded-run classes: `UNCHANGED`, `EXPECTED_CHANGE`, `POSSIBLE_REGRESSION`, `CONFIRMED_REGRESSION`, `UNCERTAIN`.

`likely_source`: `CODE` | `PROMPT` | `CONFIG` | `TOOL` | `MODEL` | `PROVIDER` | `ORACLE` | `ENVIRONMENT` | `UNKNOWN` (heuristic, not causal). `drift_kind` retains the longer snake_case labels.

## Also JSON

`health`, `debt`, `flaky` / `flake-report`, `benchmark`, `benchmark competitive`, `experiment`, `experiment-matrix`, `redteam`, `mutate`, `cluster`, `compress-failures`, `competitive-benchmark`, `maintain`.

`--format json` writes UTF-8 JSON to stdout (not wrapped by Rich tables).

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | success |
| 2 | missing file, bad YAML/JSON, duplicate IDs, empty suite, unknown test id |
| 3 | `--strict` / policy / gate failure |
| 4 | internal (corrupt store after recovery failed, unexpected) |

## `evaltrim status --format json`

```
project, suite_size, active_tests, recommendations{KEEP,MERGE,RETIRE,REVIEW},
flaky[], stale[], conflicts[], critical_coverage, evaluation_debt, suite_health,
recent_regressions[], note
```

## `evaltrim analyze --format json`

`AnalysisResult` pydantic dump: `summary`, `coverage`, `evidence`, `pairs`, `witnesses`, `recommendations` (each with `evidence` ledger), `conflicts`, `timings`, `methodology`.

Recommendation `evidence` ledger:

```
decision, semantic_similarity, behavior_overlap, unique_witnesses_lost,
critical_coverage_lost, requirement_coverage_lost, historical_failure_contribution,
counterfactual_coverage_loss, counterfactual_status, oracle_status, notes
```

## `evaltrim explain ID --suite PATH --format json`

```
id, kind, verdict, unique_witness, critical, other_tests_covering_same_behavior,
removal_simulation, evidence, reasons, flake, summary
```

## `evaltrim impacted-tests SUITE PATHS --format json`

```
{ "tests": [ { test_id, priority, evidence[], note } ], note }
```

`priority`: `CRITICAL` | `DIRECT` | `RISKY` | `ADJACENT` | `LOW_PRIORITY`. Heuristic.

## `evaltrim gate SUITE --format json`

```
mode, strict, changed_paths, selected_tests, impacted, problems, note
```

Does not run the agent.

## `evaltrim doctor --format json`

```
overall (PASS|WARN|FAIL), checks[{name,status,detail}], network
```

## `evaltrim regression` / `compare-runs`

Recorded-run classes: `EXPECTED_CHANGE`, `POSSIBLE_REGRESSION`, `CONFIRMED_REGRESSION`, `UNCERTAIN`.
