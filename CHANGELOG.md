# Changelog

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
