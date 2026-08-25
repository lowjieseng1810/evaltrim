# Scoring

The **value score** is a heuristic in `[0, 100]`. It is not a statistical estimator and must not be treated as one.

## Formula

```
value = 100 * (
    0.25 * criticality
  + 0.25 * uniqueness
  + 0.20 * historical failure signal
  + 0.15 * information (behavior richness)
  + 0.10 * change sensitivity
  + 0.05 * inverse execution cost
)
```

| Term | Meaning |
| --- | --- |
| criticality | 1 if the signature is critical, else 0 |
| uniqueness | unique atoms, scaled |
| failure signal | failure rate from optional `run_stats`, or a 0.15 prior if missing |
| information | how many behavior atoms the case carries |
| sensitivity | 1 if boundary / ambiguous / confirmation / destructive conditions are present |
| inverse cost | 1 minus normalized `estimated_cost_usd` |

Missing run history does **not** zero the score. Offline suites remain first-class.

## Redundancy weights

Default mix (must sum to 1.0):

| Factor | Weight |
| --- | --- |
| semantic (TF-IDF cosine on `input`) | 0.35 |
| behavior overlap (Jaccard of atoms) | 0.30 |
| expected-oracle similarity (TF-IDF on `expected`) | 0.20 |
| historical overlap (failure-rate closeness) | 0.15 |

Override under `config.weights` in the suite file. A high pair score never implies automatic removal.
