# EvalTrim 0.6.0 Release Audit

Date: 2026-08-25  
Version: **0.6.0** (not 1.0.0 — CLI/JSON are stable enough for agents but still beta)

## Gates

| Gate | Result |
| --- | --- |
| pytest | **101 passed** |
| ruff check | pass |
| ruff format --check | pass |
| mypy `src/evaltrim` | pass |
| `python -m build` | `evaltrim-0.6.0` sdist + wheel |

## Quality (constructed suites, no LLM, embeddings off)

| Suite | P | R | F1 | Retirement safety | Critical coverage |
| --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

Recall before (v0.4.0): customer_support **0.875**. After: **1.0**. Precision stayed 1.0. Safety stayed 1.0.

Ground truth YAML was not edited to chase scores.

## Performance

v0.4.0 5000 tests: **466.7s**, ~**315s** per-test `compute_coverage` removal, peak **614.7 MiB**.

v0.6.0 cold (`EVALTRIM_NO_CACHE=1`), same generator:

| n | runtime | peak MiB | pairs | removal_s (includes recommend loop) | similarity_s |
| --- | --- | --- | --- | --- | --- |
| 100 | 2.84s | 7.8 | 4950 | 0.08 | 2.71 |
| 500 | 13.79s | 77.0 | 21840 | 1.36 | 11.48 |
| 1000 | 28.51s / 27.61s | 139 | 38881 | 4.26 / 4.07 | 21.0 / 20.5 |
| 5000 | **249.3s** | 627.7 | 174694 | 87.6 | 98.2 |

5000 wall clock **466.7s → 249.3s** (~47% faster). Remaining cost is **blocked-pair similarity** (~98s) and **candidate generation** (~59s), not full coverage rebuilds per test.

**10,000:** not completed. A run including 10k was still executing after **8+ minutes** (expected ~2× the 5k similarity/blocking work). Stopping it was a time tradeoff, not a hidden failure. Do not invent a 10k number.

**Incremental (n=400, 5 tests edited, pair cache on):** first 3.73s (0 hits / 19817 misses); second **1.52s** (19097 hits / 720 misses). Full analysis cache does not hit when content changes.

## v0.5

- `--format json` on status, analyze, regression, impacted-tests, maintain, health, debt, flaky, explain, benchmark, gate, doctor, experiment
- `explain`, `status`, `gate --fast/--strict`
- impacted-tests: DIRECT / ADJACENT / CRITICAL / RISKY + evidence
- experiments (recorded runs, cache)
- portfolio budgets + 1-opt swap
- evidence ledger on recommendations
- optional `mcp_adapter.dispatch` (5 tools)

## v0.6

- SQLite store + `store-reset`
- analysis + pair-score cache with algorithm versions
- `evaltrim doctor`
- policy validation (unsafe retirement confidence, merge ≥ redundancy)
- CLI errors for bad YAML/JSON, duplicates, empty suite, traces
- pathlib / Windows-style impacted paths
- `shell=False` command adapter
- default no network

## Screenshots

Real CLI captures under `docs/images/` (SVG + source `.txt`, HTML report).

## Remaining limitations

See README “Not guaranteed” and `docs/limitations.md`. No IDE, no hosted SaaS, no auto-retirement, no causal drift proof.
