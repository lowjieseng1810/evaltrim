# Changelog

## 0.7.0 — 2026-08-25

Competitive parity pass: measure, close gaps, re-measure. No “beats every competitor” claim.

- Plugin graders: not_contains, JSON Schema subset, tool_args, TTFT, tokens, custom `module:fn`, trajectory LCS/strict
- Statistics: stdev, percentiles, bootstrap CI, Welch t-test, Cohen's d, statistical vs practical significance
- Regression: `UNCHANGED`; provider/infrastructure errors are not `CONFIRMED_REGRESSION`
- Flakes: `ENVIRONMENTAL` vs model/agent flake
- Experiments: multi-run matrix, Pareto BEST_QUALITY / BEST_COST / BEST_LATENCY / BEST_PARETO_OPTION
- Intelligence: behavior classes, information gain, failure-detection value, mutation score, proof graphs
- Production failure compression (never auto-inserts)
- Local red-team family probes; minimal local sandbox; multi-turn scenario replay
- YAML/JSON/JSONL export; versioned JSON contract `1.0`
- Scale: DF-capped blocking + cached token vectors (see benchmark.md for measured times)
- Competitive audit + harness (`docs/competitive-benchmark.md`)

## 0.6.0 — 2026-08-25

Agent-native workflow and release infrastructure.

- Indexed counterfactual removal (same safety decisions as coverage-exclusion reference)
- Stronger offline paraphrase matching without lowering the global merge bar
- `status`, `explain`, `gate`, `doctor`, `experiment`, `regression`/`flaky` aliases
- JSON on important commands; evidence ledger on recommendations
- SQLite history/cache; pair-score incremental reuse; cache invalidation tests
- Policy validation (unsafe retirement confidence, impossible thresholds)
- CLI errors for missing/malformed suites, traces, policies
- Tiny optional MCP dispatcher
- `evaltrim doctor` PASS/WARN/FAIL
- Portfolio: greedy + one optional swap, budget constraints, per-id evidence

## 0.4.0

Behavior graph, unique witnesses, health/debt, portfolio (greedy), GitHub artifacts, evidence ledger.

## 0.3.0

Traces, run classification, watch, impacted-tests, flake states, failure candidates.

## 0.2.0

Layered similarity, normalization, optional hashing embeddings.
