# EvalTrim

**Prove which AI-agent evals are worth keeping.**

EvalTrim is the evaluation control plane for AI agents.

Don't just evaluate your agent. Maintain the evaluation system itself.

It is a **local-first** CLI. It does not replace your agent runtime or a generic eval harness. It sits beside them and answers: which tests are unique, which are redundant, what a removal would break, and what to run after a change. It never deletes tests. Recommendations are `KEEP` / `MERGE` / `RETIRE` / `REVIEW`, each with a serializable evidence ledger.

## Why this exists

AI-agent evaluation suites grow quickly. Paraphrases, stale oracles, flaky history, conflicting expected outputs, and low-value cases accumulate. Deleting a test *feels* cheap until it was the only remaining witness for a critical behavior. EvalTrim makes that loss visible **before** anyone edits the suite.

## What makes it different

1. **Unique behavioral witnesses** — the only remaining test for a behavior, boundary, requirement, or failure family.
2. **Counterfactual removal** — simulate deleting a test and measure coverage that would actually disappear.
3. **Evidence-backed maintenance** — every recommendation carries overlap, witness loss, and a removal verdict.
4. **Suite health / evaluation debt** — labeled heuristics for maintainers, not scores you can game.
5. **Portfolio optimization** — a greedy + 1-opt subset under cost / time / count budgets.
6. **Production failure compression** — cluster failures into candidate tests; nothing is auto-inserted.
7. **Local-first execution** — no hosted backend, no telemetry by default.

Similarity may **create candidates**. It does **not** independently authorize `RETIRE`.

## Core workflow

```
Agent → Evaluation → Trace → Behavior → Witnesses → Counterfactual → Evidence → Maintenance
```

RUN → RECORD → GRADE → COMPARE → DETECT → EXPLAIN → OPTIMIZE → MAINTAIN

## What it does

### Evaluate

Plugin graders (exact, contains, regex, JSON Schema, numeric tolerance, tools, trajectories, latency, cost, custom), multi-turn scenarios, statistics, experiment matrix.

### Regress

Snapshots, replay, run classes including `UNCHANGED`, drift notes, flaky history (`ENVIRONMENTAL` vs model flake). A provider error is not a confirmed model regression.

### Understand

Behavior graph, unique witnesses, requirements, oracle health, oracle conflicts.

### Optimize

Suite minimization, information gain, portfolio / Pareto, evaluation debt.

### Maintain

Evidence-backed `KEEP` / `MERGE` / `REVIEW` / `RETIRE`. EvalTrim never rewrites the suite file.

## 30-second demo

```bash
git clone https://github.com/lowjieseng1810/evaltrim.git
cd evaltrim
python3 -m pip install -e ".[dev]"
evaltrim analyze examples/demo_suite.yaml
```

Representative output from that command (constructed demo suite, not production traffic):

```
# EvalTrim Report

## Summary

12 tests analyzed
5 recommended KEEP
3 MERGE
0 RETIRE
4 REVIEW

Critical behavior coverage:
100.0%

Unique Witnesses

- `privacy-delete`: condition:destructive, domain:privacy, state:unauthenticated
- `refund-boundary`: condition:amount_at_limit, condition:policy_boundary, condition:threshold_equality
```

Full script: [`scripts/demo-public.sh`](scripts/demo-public.sh).

## The key idea

1. **Similarity creates candidates** (paraphrases, near-duplicates).
2. **Behavioral evidence determines safety** (atoms, requirements, critical flags).
3. **Counterfactual analysis checks what would actually be lost** if the test disappeared.

A rare lexical token on a duplicate behavior is not a unique witness. Exclusive coverage is.

## Example

On `examples/demo_suite.yaml`:

| Test | Recommendation | Why |
| --- | --- | --- |
| `privacy-delete` | **KEEP** | Unique privacy / destructive witness. Removing it drops critical coverage 100% → 80%. Verdict: KEEP. |
| `refund-002b` | **MERGE** | Near-duplicate of the $700 refund escalation. Removal leaves coverage 100% / 100%. Verdict: SAFE_TO_RETIRE (still not auto-deleted). |

```bash
evaltrim explain privacy-delete --suite examples/demo_suite.yaml
evaltrim simulate-remove examples/demo_suite.yaml privacy-delete
evaltrim simulate-remove examples/demo_suite.yaml refund-002b
```

## Measured results

Constructed / labeled suites. **Not** production correctness. Ground truth was not rewritten to chase scores. See [docs/benchmark.md](docs/benchmark.md).

| Metric | Value | Dataset |
| --- | --- | --- |
| Unique-witness precision | 1.0 | Labeled constructed suites including `benchmarks/witness_final/` |
| Unique-witness recall | 1.0 | same |
| Critical witness recall | 1.0 | same |
| False critical witnesses | 0 | same |
| Retirement safety | 1.0 | same + coding / support / shopping |
| Critical coverage | 1.0 | same |
| 10k cold runtime | **54.7049s** | Synthetic generator, `EVALTRIM_NO_CACHE=1` |
| Incremental 10k / 5 changed | **2.0613s** | Pair cache already populated; empty-cache incremental was ~10.4s |

Redundancy P/R/F1 on coding / customer_support / shopping constructed suites: **1.0**.

## Competitive position

EvalTrim reaches **parity on the measured common evaluation dimensions** and adds an evaluation-suite intelligence layer focused on witness analysis, counterfactual maintenance, and suite optimization.

Some competitor dimensions remain **UNMEASURED** or **NOT DIRECTLY COMPARABLE** (competitor 10k scale, live Promptfoo plugin catalogs vs detection quality, DeepEval LLM judges, EvalView GUI, hosted SaaS). UNMEASURED is not a win. NOT OFFERED is not a competitor zero.

Status: **VERIFIED PARITY ON MEASURED DIMENSIONS** — not a claim of universal superiority.

Details: [docs/competitive-results.md](docs/competitive-results.md) · [docs/competitive-methodology.md](docs/competitive-methodology.md) · [docs/limitations.md](docs/limitations.md)

## Screenshots

Generated from the current 1.0.0 CLI on `examples/demo_suite.yaml`. Not mocked numbers.

### Main CLI

![evaltrim analyze](docs/images/01-main-cli.svg)

### Unique witness

![evaltrim explain](docs/images/02-unique-witness.svg)

### Counterfactual removal

![simulate-remove](docs/images/03-removal-simulation.svg)

### Suite health

![evaltrim health](docs/images/04-suite-health.svg)

### Regression

![evaltrim compare](docs/images/05-regression.svg)

### GitHub PR comment

![analyze --format github](docs/images/06-github-pr.svg)

## Architecture

```
CLI
 → Core evaluation model (records, graders, scenarios)
 → Traces / history (local SQLite)
 → Behavior graph
 → Intelligence engine (witnesses, counterfactuals, portfolio)
 → Evidence / proof graph
 → Reports / CI
```

## Privacy

- Local-first. No hosted backend required.
- No telemetry by default.
- Optional embeddings / LLM judges run only when you enable them.
- See [docs/privacy.md](docs/privacy.md) and [docs/network.md](docs/network.md).

## Installation

```bash
python3 -m pip install -e ".[dev]"
evaltrim doctor
```

Python 3.11+. Windows, macOS, and Linux. Default path is offline.

## CI / GitHub Actions

Workflow: [`.github/workflows/evaltrim.yml`](.github/workflows/evaltrim.yml)

```yaml
- run: pip install .
- run: evaltrim analyze examples/demo_suite.yaml --format github
```

The action writes artifacts and a short PR comment. EvalTrim never deletes tests from the repo.

## Documentation

- [Architecture](docs/architecture.md)
- [Removal simulation](docs/removal-simulation.md)
- [Evidence](docs/evidence.md)
- [Health](docs/health.md)
- [GitHub Action](docs/github-action.md)
- [JSON contract](docs/json.md)
- [Graders](docs/graders.md)
- [Limitations](docs/limitations.md)
- [Changelog](CHANGELOG.md)
- [Release 1.0](docs/release-1.0.md)
- [GitHub copy](docs/github-copy.md)

## Limitations

- Local sandbox is **not** VM / container isolation.
- LLM judge requires a provider you configure.
- Some semantic matching remains a heuristic.
- Some competitor dimensions are unmeasured.
- No hosted SaaS.
- No automatic deletion.

## License

[MIT](LICENSE)
