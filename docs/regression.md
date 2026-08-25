# Regression control

## Suite snapshots

`evaltrim snapshot save|list|compare` and `evaltrim compare` diff **suite analyses** (coverage, recommendations). They do not claim live-agent regressions.

## Recorded runs

`evaltrim compare-runs baseline.json current.json` compares outputs, semantic output, tool calls/args, trajectory, grader scores, latency, cost, tokens.

Classes: `EXPECTED_CHANGE`, `POSSIBLE_REGRESSION`, `CONFIRMED_REGRESSION`, `UNCERTAIN`. Not every difference is a regression.

## Drift

`LIKELY_SOURCE` with confidence: code, prompt, configuration, tool schema, model/provider, test/oracle, or uncertain. This is **not** causal attribution.

Oracle-text changes vs agent-output changes are distinguished when those fields are present.
