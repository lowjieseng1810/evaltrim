# EvalTrim 1.0.0

Local-first evaluation control plane for AI agents. Shipped 2026-08-26.

## What shipped

- Evaluation runner: graders, tool/trajectory checks, multi-turn scenarios, statistics, experiment matrix
- Regression control: snapshots, replay, `UNCHANGED`, provider errors ≠ confirmed model regressions, flakes including `ENVIRONMENTAL`
- Evaluation suite intelligence: unique witnesses, counterfactual removal, suite health, evaluation debt, portfolio / Pareto, information gain, failure compression, evidence ledger
- GitHub Action, JSON contract `1.0`, local sandbox (process, not a VM), local red-team family probes
- Competitive verification harness with isolated competitor environments; status **VERIFIED PARITY ON MEASURED DIMENSIONS**

It never deletes tests.

## Benchmark highlights (constructed / labeled, not production)

| Metric | 1.0.0 |
| --- | --- |
| Unique-witness precision / recall | 1.0 / 1.0 |
| Critical witness recall | 1.0 |
| False critical witnesses | 0 |
| Retirement safety | 1.0 |
| Critical coverage | 1.0 |
| 10k cold (`EVALTRIM_NO_CACHE=1`) | 54.7049s, ~416.5 MiB |
| Incremental 10k / 5 changed (warm pair cache) | 2.0613s |

See [docs/benchmark.md](benchmark.md) and [docs/competitive-results.md](competitive-results.md).

## Compatibility

- Python ≥ 3.11
- CLI: `evaltrim`
- Import: `evaltrim`
- JSON `contract_version`: `1.0`

## Known limitations

- Local sandbox is not VM isolation
- LLM judge needs a provider if enabled
- Semantic matching is a heuristic by default
- Some competitor dimensions remain UNMEASURED / NDC
- No hosted SaaS
- No automatic deletion

## Upgrade notes

There is no prior public 0.x install path to migrate. Clone the repo and `pip install -e ".[dev]"`.

## Presentation (same version)

README, screenshots, and launch copy were finalized after the engineering freeze. No evaluation algorithms or benchmark ground truth were changed in that pass.
