# Benchmarks

Quality and scale numbers for **0.6.0** are measured, not invented. See also the README and `RELEASE_AUDIT.md`.

## Quality (v0.6.0, no LLM, embeddings off, `EVALTRIM_NO_CACHE=1`)

| Suite | Precision | Recall | F1 | Retirement safety | Critical coverage | Suite reduction |
| --- | --- | --- | --- | --- | --- | --- |
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.46 |
| customer_support | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.25 |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.40 |

v0.4.0 customer_support recall was 0.875 (`parcel is late` vs `parcel arrived late`). Precision and safety stayed 1.0 after the recall fix. Hard negatives are **not** merged.

Ground truth files were not rewritten to inflate scores.

## Scale (synthetic, first cold 0.6 run before coverage-delta micro-opt)

| n | runtime | peak MiB | pairs | removal_s | similarity_s |
| --- | --- | --- | --- | --- | --- |
| 100 | 2.84 | 7.8 | 4950 | 0.08 | 2.71 |
| 500 | 13.79 | 77.0 | 21840 | 1.36 | 11.48 |
| 1000 | 28.51 | 138.7 | 38881 | 4.26 | 21.03 |
| 5000 | 249.3 | 627.7 | 174694 | 87.6 | 98.2 |

10,000 was not completed (wall time). Incremental n=400: 3.73s → 1.52s after five edits (19097 pair-cache hits).

Command:

```bash
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --format json
EVALTRIM_NO_CACHE=1 PYTHONPATH=src python3 -m evaltrim.cli benchmark benchmarks --scale 100,500,1000,5000 --format json
```
