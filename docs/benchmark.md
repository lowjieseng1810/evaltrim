# Benchmarks

Quality and scale numbers for **0.7.0** are measured, not invented. See also the README, `RELEASE_AUDIT.md`, and `docs/competitive-results.md`.

## Quality (v0.7.0, no LLM, embeddings off, `EVALTRIM_NO_CACHE=1`)

| Suite | Precision | Recall | F1 | Retirement safety | Critical coverage | Suite reduction |
| --- | --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.46 |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.25 |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.40 |

Same as v0.6.0 on this harness. Ground truth files were not rewritten.

v0.4.0 customer_support recall was 0.875. Precision and safety stayed 1.0 after the recall fix.

## Scale (synthetic, cold, `EVALTRIM_NO_CACHE=1`)

v0.6.0 5k: **249.3s**, 174694 pairs, 10k not completed.

v0.7.0 (DF-capped blocking):

| n | runtime | peak MiB | pairs | removal_s | similarity_s |
| --- | --- | --- | --- | --- | --- |
| 100 | 2.65 | 8.2 | 4950 | 0.09 | 2.50 |
| 500 | 11.51 | 72.0 | 19856 | 1.42 | 9.61 |
| 1000 | 19.44 | 100.9 | 27379 | 4.40 | 13.78 |
| 5000 | **133.4** | 257.1 | 59840 | 97.66 | 30.60 |
| 10000 | **436.8** | 408.6 | 76205 | 387.45 | 38.33 |

10k completes. Remaining cost is per-test counterfactual simulation, not candidate generation.

Command:

```bash
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --format json
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --scale 100,500,1000,5000,10000 --format json
PYTHONPATH=src python3 -m evaltrim.cli competitive-benchmark --format json
```
