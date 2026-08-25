# Benchmarks

Constructed suites: `benchmarks/{coding_agent,customer_support,shopping_agent}/`.

```bash
evaltrim benchmark benchmarks
evaltrim benchmark benchmarks --scale 100,500,1000,5000
```

## Quality (v0.4.0, no LLM, embeddings off)

| Suite | P | R | F1 | Retirement safety | Critical coverage | Reduction |
|---|---|---|---|---|---|---|
| coding_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 46% |
| customer_support | 1.0 | 0.875 | 0.93 | 1.0 | 1.0 | 19% |
| shopping_agent | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 40% |

v0.2.0 recall on the previous (smaller) suites was 0.50 / 0.40 / 0.25 with precision 1.0.

Missed customer_support pair: lexical paraphrase `parcel is late` vs `parcel arrived late` (MERGE requires high semantic + full behavior overlap + similar expected). Hard negatives are **not** merged.

Reduction is a review-queue share (MERGE+RETIRE), not deletions.

## Scale (synthetic, 2026-08-25)

| n | runtime | peak MiB | pairs |
|---|---|---|---|
| 100 | 2.68s | 7.3 | 4950 |
| 500 | 15.09s | 75.5 | 21840 |
| 1000 | 35.69s | 136.5 | 38881 |
| 5000 | 466.7s | 614.7 | 174694 |

10,000 not run. Bottleneck at 5,000: per-test removal simulation (~315s).
