# Policies

Optional `evaltrim.yaml` (walks parents from the suite directory):

```yaml
policies:
  minimum_critical_coverage: 1.0
  max_behavior_coverage_drop: 0.01
  minimum_retirement_confidence: 0.80
  fail_on_oracle_conflict: true
```

```bash
evaltrim check examples/demo_suite.yaml --config examples/evaltrim.yaml
evaltrim analyze examples/demo_suite.yaml --strict
```

Exit codes (stable):

| Code | Meaning |
| --- | --- |
| 0 | pass |
| 2 | invalid input / missing file |
| 3 | policy / strict violation |
| 4 | unexpected internal error |
