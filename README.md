# EvalTrim

> The Evaluation Control Plane for AI Agents.

Run. Replay. Compare. Understand. Optimize. Maintain.

EvalTrim is a **local-first** CLI for AI-agent eval suites. It does not replace your agent runtime or a generic eval harness. It sits beside them and answers: which tests are unique, which are redundant, what a removal would break, and what to run after a change.

It never deletes tests. Recommendations are `KEEP` / `MERGE` / `RETIRE` / `REVIEW` / `ADD_CANDIDATE`, each with a serializable evidence ledger.

Current version: **0.7.0** (beta public API — not 1.0). Competitive status: **PARITY** — see [docs/competitive-results.md](docs/competitive-results.md). This is not a claim that EvalTrim beats every competitor on every metric.

## Three layers

1. **Evaluation** — plugin graders (exact, contains, regex, JSON Schema, semantic, tools, trajectory, latency, TTFT, tokens, cost, custom), record, replay, multi-run statistics, experiment matrix / Pareto.
2. **Regression Control** — recorded-run classes including `UNCHANGED`, drift attribution (heuristic), watch, impacted tests + safety sample, flakes including `ENVIRONMENTAL`, pre-commit `gate`.
3. **Evaluation Intelligence** — behavior classes, unique witnesses, counterfactual removal, information gain, mutation score, suite health, evaluation debt, portfolio / Pareto, proof-carrying recommendations.

EvalTrim does not only evaluate the agent. It evaluates and maintains the evaluation system itself.

## What makes it different

These are complementary to Promptfoo, LangSmith, Braintrust, and similar tools — not a claim of inventing evaluation:

- **Behavior graph** — tests as coverage over normalized behavior atoms.
- **Unique witnesses** — the only remaining test for a behavior, boundary, requirement, or failure family.
- **Counterfactual removal** — simulate deleting a test *before* anyone deletes it.
- **Suite health** and **evaluation debt** — heuristic diagnostics, not scores you can game.
- **Evidence ledger** — every recommendation carries similarity, overlap, witness loss, and removal verdict.
- **Portfolio optimization** — a explainable greedy + 1-opt subset under cost / time / count budgets.

Semantic similarity may **create candidates**. It does **not** independently authorize `RETIRE`.

## 30-second workflow

```bash
git clone <this-repo>
cd evaltrim
python3 -m pip install -e ".[dev]"
evaltrim init evals.yaml
evaltrim analyze evals.yaml
evaltrim health evals.yaml --format json
evaltrim regression examples/demo_suite.yaml examples/demo_suite.yaml --format json
evaltrim maintain evals.yaml
evaltrim explain privacy-delete --suite examples/demo_suite.yaml
evaltrim doctor
```

Use `examples/demo_suite.yaml` if you want a populated suite immediately.

## Semantic matching (honest)

| Mode | How to enable | Network |
| --- | --- | --- |
| **DEFAULT** | nothing | none — normalized tokens, n-grams, rare-token weights, behavior overlap, unique witnesses, counterfactual removal |
| **OPTIONAL EMBEDDING** | `EVALTRIM_EMBEDDINGS=1` or `config.embeddings_enabled` | none — local hashing encoder (no model download) |
| **OPTIONAL LLM** | `EVALTRIM_LLM=1` / `config.llm_enabled` plus a provider you configure | only then |

The default merge bar is **not** lowered globally. Hard negatives that share vocabulary but differ in behavior stay unmerged (refund vs refund + store credit).

## Agent-native CLI

Every important command accepts `--format json` with stable field names:

`status` · `analyze` · `regression` · `impacted-tests` · `maintain` · `health` · `debt` · `flaky` · `explain` · `benchmark` · `gate` · `doctor` · `experiment` · `experiment-matrix` · `redteam` · `mutate` · `cluster` · `competitive-benchmark`

JSON objects include `contract_version` (`1.0`). Extra keys may appear.

Exit codes: `0` ok · `2` invalid/missing input · `3` policy/strict · `4` internal.

Optional tiny MCP-style adapter (`evaltrim.mcp_adapter.dispatch`): `get_status`, `impacted_tests`, `explain`, `regression_summary`, `suggest_maintenance`. Not required. Not a platform.

## Screenshots (actual CLI output)

Generated from this repo’s demo suite. Not mocked numbers.

### Main CLI

![CLI evaluation summary](docs/images/cli-main.svg)

### Unique witness (why a test is kept)

![Unique witness](docs/images/unique-witness.svg)

### Removal simulation (SAFE vs KEEP)

![Removal simulation](docs/images/removal-simulation.svg)

### Suite health / evaluation debt

![Suite health](docs/images/suite-health.svg)

![Evaluation debt](docs/images/evaluation-debt.svg)

### Regression

![Regression](docs/images/regression.svg)

### GitHub PR comment (rendered from `--format github`)

![GitHub PR comment](docs/images/github-pr-comment.svg)

### HTML report

Open [docs/images/report.html](docs/images/report.html).

## Measured quality (v0.7.0)

Command: `EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks`  
No LLM. Embeddings off. Constructed suites — **not** production traffic.

Re-measured after the 0.7 pass (same metadata, same merge bar). Numbers below are filled from the latest local run in [docs/benchmark.md](docs/benchmark.md).

v0.6.0 on the same harness was already precision/recall/safety/critical coverage **1.0** on those three suites. The 0.7 bar is: keep those safety metrics while adding graders/stats and reducing scale runtime.

## Competitive comparison

See [docs/competitive-benchmark.md](docs/competitive-benchmark.md) and [docs/competitive-results.md](docs/competitive-results.md).

Competitor columns that were not reproduced in-process are **UNMEASURED**. EvalTrim is **not** declared superior to EvalView snapshots, Promptfoo red-team catalogs, Vercel coding sandboxes, or hosted experiment UIs.

| Suite | Precision | Recall | F1 | Retirement safety | Critical coverage | Suite reduction |
| --- | --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 46% |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 25% |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 40% |

Recall **before** this pass (v0.4.0, same harness): customer_support **0.875** (missed `parcel is late` / `parcel arrived late`). Precision and retirement safety stayed **1.0**. We did not lower the global merge threshold; normalization + content-token overlap was enough for that pair without collapsing the store-credit hard negative.

v0.2.0 recall on smaller suites was coding 0.50 / customer_support 0.40 / shopping 0.25.

## Scale (synthetic suites, no quality labels)

Cold run, `EVALTRIM_NO_CACHE=1`. v0.6.0 5,000-test runtime was **249.3s** with 174k candidate pairs. v0.7 caps inverted-index document frequency and neighbor retrieval on large n.

Latest measured numbers:

| n | runtime | peak MiB | pairs |
| --- | --- | --- | --- |
| 100 | 2.65s | 8.2 | 4950 |
| 500 | 11.51s | 72 | 19856 |
| 1000 | 19.44s | 101 | 27379 |
| 5000 | **133.4s** (was 249.3s in 0.6.0) | 257 | 59840 |
| 10000 | **436.8s** (not completed in 0.6.0) | 409 | 76205 |

Details: [docs/benchmark.md](docs/benchmark.md).

## Not guaranteed

- Detecting every unknown behavior
- Offline semantic similarity is a heuristic, not an embedding model
- Drift “likely source” is not causal proof
- Benchmark scores do not imply production correctness
- Automatic retirement is **never** performed
- Impacted-test selection is not a complete call graph
- Optional MCP is a thin dispatcher, not an IDE

Deferred on purpose: IDE plugins, full MCP platform, self-healing, automatic repair, canary/rollback, hosted SaaS.

## Docs

- [Architecture](docs/architecture.md)
- [JSON for coding agents](docs/json.md)
- [Network & privacy](docs/network.md)
- [Cache & storage](docs/cache.md)
- [Semantic backends](docs/semantic.md)
- [MCP adapter](docs/mcp.md)
- [Removal simulation](docs/removal-simulation.md)
- [Competitive audit](docs/competitive-benchmark.md)
- [Taxonomy A–AP](docs/taxonomy.md)
- [Competitive results](docs/competitive-results.md)
- [Limitations](docs/limitations.md)
- [Changelog](CHANGELOG.md)
- [Release audit](RELEASE_AUDIT.md)

## License

[MIT](LICENSE)
