# Benchmarks

Quality and scale numbers for **1.0.0** are measured, not invented. See also the README and `docs/competitive-results.md`.

## Quality (v1.0.0, no LLM, embeddings off, `EVALTRIM_NO_CACHE=1`)

Immutable metadata on coding / customer_support / shopping / robustness / witness was not rewritten to chase scores.

Unique-witness precision/recall on those labeled suites is ≥ 0.95. Critical witness recall is 1.0. False critical witnesses are 0. Retirement safety and critical coverage stay 1.0.

Redundancy P/R/F1 on coding / customer_support / shopping remains 1.0.

## Scale

## Scale

v0.9.0 10k: **~57s**. v1.0.0 10k (cold `EVALTRIM_NO_CACHE=1`): **55.63s**, peak **416.5 MiB**, 76205 pairs.

Incremental (pair cache on): 10,000 tests, 5 changed → **10.36s** (75579 pair hits / 626 misses). Cold warm-up of the same suite with cache allowed: **20.27s**.

## Quality (v0.9.0, no LLM, embeddings off, `EVALTRIM_NO_CACHE=1`)

Immutable metadata on coding / customer_support / shopping was not rewritten.

| Suite | Precision | Recall | F1 | Retirement safety | Critical coverage |
| --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| robustness | n/a (no pair labels) | n/a | n/a | 1.0 | 1.0 |

Paraphrase vs hard-negative semantic checks live in `tests/test_v09.py`.

## Scale (synthetic, cold, `EVALTRIM_NO_CACHE=1`)

v0.7.0 10k: **436.8s**. v0.9.0 10k: **56.7s** (indexed unique-critical + sim cache + no tier-2 hashing above 400 tests).

| n | runtime | peak MiB | pairs | simulations_executed | removal_s | similarity_s |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | 5.42 | 9.6 | 4950 | 1 | 0.06 | 5.28 |
| 500 | 11.17 | 72.1 | 19856 | 1 | 0.52 | 10.26 |
| 1000 | 16.19 | 101.1 | 27379 | 1 | 0.74 | 14.58 |
| 5000 | **38.94** | 257.5 | 59840 | 1 | 2.82 | 31.96 |
| 10000 | **56.75** | 409.2 | 76205 | 1 | 5.35 | 41.64 |

`simulations_executed=1` on this generator means equivalent-class reuse: most synthetic tests share an empty unique-atom signature. Safety math is unchanged; constructed-suite P/R/safety stayed 1.0.

n=100 is slower than v0.7 because tier-2 hashing runs on small suites.

Command:

```bash
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --format json
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --scale 100,500,1000,5000,10000 --format json
PYTHONPATH=src python3 -m evaltrim.cli competitive-benchmark --format json
```
