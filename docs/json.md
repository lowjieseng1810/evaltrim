# JSON for coding agents

Stable enough for tools. Field names below are part of the 0.6 contract. Extra keys may appear; do not require unknown keys to be absent.

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
