# EvalTrim 0.7.0 Release Audit

Date: 2026-08-25  
Version: **0.7.0** (not 1.0.0 — competitive status is PARITY, not SUPERIOR)

## Gates

| Gate | Result |
| --- | --- |
| pytest | **112 passed** (re-count in this audit) |
| ruff check | pass |
| ruff format --check | pass |
| mypy `src/evaltrim` | pass |
| `python -m build` | `evaltrim-0.7.0` sdist + wheel |

## Competitive status

**B. PARITY** — no measured head-to-head metric is worse, because competitor numeric cells were **UNMEASURED**. Superiority is not claimed.

See `docs/competitive-benchmark.md` and `docs/competitive-results.md`.

## Quality (constructed suites, no LLM, embeddings off)

| Suite | P | R | F1 | Retirement safety | Critical coverage |
| --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

Safety metrics unchanged vs 0.6.0. Ground truth YAML was not edited.

Internal fixtures: mutation score 0.857; security probe detection 1.0 with 0 false positives; identical samples do not flag statistical regression; provider errors are not `CONFIRMED_REGRESSION`.

## Performance

v0.6.0 5k: **249.3s**, 174694 pairs. 10k not completed.

v0.7.0 cold (`EVALTRIM_NO_CACHE=1`):

| n | runtime | peak MiB | pairs |
| --- | --- | --- | --- |
| 100 | 2.65s | 8.2 | 4950 |
| 500 | 11.51s | 72.0 | 19856 |
| 1000 | 19.44s | 100.9 | 27379 |
| 5000 | **133.4s** | 257.1 | 59840 |
| 10000 | **436.8s** | 408.6 | 76205 |

5k ~47% faster than 0.6. 10k completes. 10k is dominated by per-test removal simulation (~387s).

Competitor wall times on this generator: **UNMEASURED**.

## Remaining limitations

EvalView snapshot UX, Promptfoo red-team catalog depth, Vercel coding sandboxes, and hosted experiment UIs are not claimed beaten. See README.
