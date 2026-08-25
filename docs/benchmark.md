# Benchmarks

Constructed suites live under `benchmarks/`:

- `customer_support/`
- `coding_agent/`
- `shopping_agent/`

Each directory has `suite.yaml` plus `benchmark_metadata.yaml` describing intended redundant groups, unique witnesses, and critical cases.

## Runner

```bash
evaltrim benchmark benchmarks
evaltrim benchmark benchmarks/customer_support/suite.yaml --format json
```

Measured fields:

- redundancy precision / recall (pair-level vs ground truth)
- unique-witness precision / recall when listed
- retirement safety rate (1.0 if no expected critical case is marked RETIRE)
- critical coverage
- estimated suite reduction (MERGE + RETIRE share)
- runtime
- deterministic repeatability (two full analyses compare equal)

## Target metrics (goals, not claims)

| Goal | Target |
| --- | --- |
| Redundancy precision | ≥ 90% |
| Critical coverage preservation | 100% on constructed suites |
| Suite reduction | 20–40% on constructed suites |
| Runtime | < 60s for 1000 cases, excluding LLM |
| Repeatability | equivalent output on the same input |

Measured on this checkout (`evaltrim benchmark benchmarks`, local TF-IDF, no LLM):

| Suite | tests | redundancy precision | retirement safety | critical coverage | suite reduction | deterministic | runtime |
| --- | --- | --- | --- | --- | --- | --- | --- |
| coding_agent | 12 | 1.0 | 1.0 | 1.0 | 33% | yes | ~3ms |
| customer_support | 14 | 1.0 | 1.0 | 1.0 | 29% | yes | ~4ms |
| shopping_agent | 14 | 1.0 | 1.0 | 1.0 | 14% | yes | ~4ms |

Recall vs constructed groups is lower than precision (near-paraphrases are not always grouped). Shopping reduction is below the 20–40% *target band*. Treat the table as a snapshot, not a product claim.

