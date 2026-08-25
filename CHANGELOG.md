# Changelog

## 0.9.0 — 2026-08-25

Internal maturity pass (engineering target, not a public 9/10 score).

Competitive verification (same day, not a feature wave):

- Common 20-task suite under `benchmarks/competitive/`
- Version lock in `benchmarks/competitive/environment.yaml`
- Head-to-head AgentEval 0.7.0 grader/stat/flake fixtures (MEASURED)
- `evaltrim benchmark competitive --format json --competitor <name> --write-docs`
- Status **GAPS REMAIN**: Promptfoo/DeepEval/Inspect/EvalView unreproduced; no fabricated numbers

- Broader graders: numeric tolerance, set equality, JSON path, subsequence, required/forbidden tools, max steps, state predicates, LCS/strict aliases; `register_grader` documented
- Three-tier semantic (lexical / local hashing / optional encoder) with per-pair confidence; hard-negative clause penalty
- `evaltrim replay --compare` human-readable trajectory diffs (terminal/JSON/Markdown)
- Experiment verdicts RECOMMENDED / TRADEOFF / REGRESSION / INCONCLUSIVE; reproducible manifests; smoke/dry-run planning
- Provider-neutral red-team families expanded; curated local probes with detection/FP/reproducibility
- Declarative YAML scenarios (personas, state, branch, tool, assert)
- Local sandbox: env allowlist, timeouts, output caps, escape tests; labeled LOCAL SANDBOX not a VM
- Counterfactual equivalence-class cache **and** O(n) unique-critical indexing (10k **56.7s**, was 436.8s)
- Compact WHAT/WHY/EVIDENCE/RISK/ACTION reports; `--verbose` proof nodes with stable evidence IDs
- Visible `ValueWeights`; named portfolios BEST COMPACT / CRITICAL / COST-CONSTRAINED
- `evaltrim doctor` checks sandbox, config, optional deps, embeddings, GitHub
- Robustness benchmark fixture (immutable metadata)

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
