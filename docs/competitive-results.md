# Competitive results

EvalTrim **0.9.0**.

EvalTrim numbers are measured in this process. Competitor columns are UNMEASURED unless a public benchmark was reproduced in benchmarks/competitive/. Do not treat UNMEASURED as a win.

Internal maturity labels (Parity / Strong parity / Leading / Not comparable) live in `docs/internal-scorecard.md` and `docs/competitive-benchmark.md`. They are not marketing claims.

Constructed-suite precision/recall/F1/retirement safety/critical coverage remain **1.0** on coding, customer_support, and shopping (immutable metadata). Scale: 5k **38.94s**, 10k **56.75s**. Competitor runtime on the same generator: **UNMEASURED**.

EvalTrim numbers are measured in this process. Competitor columns are UNMEASURED unless a public benchmark was reproduced in benchmarks/competitive/. Do not treat UNMEASURED as a win.

| Metric | EvalTrim | Competitor | Winner | Method | Notes |
| --- | --- | --- | --- | --- | --- |
| constructed_redundancy_precision_min | 1.0 | UNMEASURED | UNMEASURED | constructed suites | Head-to-head competitor value not reproduced in this run. |
| constructed_redundancy_recall_min | 1.0 | UNMEASURED | UNMEASURED | constructed suites | Head-to-head competitor value not reproduced in this run. |
| retirement_safety_min | 1.0 | UNMEASURED | UNMEASURED | constructed suites | Head-to-head competitor value not reproduced in this run. |
| critical_coverage_min | 1.0 | UNMEASURED | UNMEASURED | constructed suites | Head-to-head competitor value not reproduced in this run. |
| grader_plugin_count | 15 | UNMEASURED | UNMEASURED | registered grader classes | Head-to-head competitor value not reproduced in this run. |
| json_schema_grader_pass | 1.0 | UNMEASURED | UNMEASURED | local fixture | Head-to-head competitor value not reproduced in this run. |
| unchanged_classification | 1.0 | UNMEASURED | UNMEASURED | identical runs | Head-to-head competitor value not reproduced in this run. |
| provider_error_not_confirmed_regression | 1.0 | UNMEASURED | UNMEASURED | provider_error fixture | Head-to-head competitor value not reproduced in this run. |
| environmental_flake_class | 1.0 | UNMEASURED | UNMEASURED | timeout/provider outcomes | Head-to-head competitor value not reproduced in this run. |
| false_statistical_regression_rate | 1.0 | UNMEASURED | UNMEASURED | identical samples must not flag | Head-to-head competitor value not reproduced in this run. |
| detect_mean_shift | 1.0 | UNMEASURED | UNMEASURED | mean +3 on n=20 | Head-to-head competitor value not reproduced in this run. |
| mutation_score | 0.8571 | UNMEASURED | UNMEASURED | constructed grader probes | Head-to-head competitor value not reproduced in this run. |
| security_detection_rate | 1.0 | UNMEASURED | UNMEASURED | local family probes | Head-to-head competitor value not reproduced in this run. |
| security_false_positives | 0 | UNMEASURED | UNMEASURED | local family probes | Head-to-head competitor value not reproduced in this run. |
| default_network_required | 0.0 | UNMEASURED | UNMEASURED | 0 means no network by default | Head-to-head competitor value not reproduced in this run. |
| json_contract_version | 1.0 | UNMEASURED | UNMEASURED | machine-readable contract | Head-to-head competitor value not reproduced in this run. |

## Scale (EvalTrim only)

Harness (this file, latest code):

- n=100 t=2.3953s mib=8.17 pairs=4950
- n=500 t=9.9603s mib=70.15 pairs=19856

Dedicated cold run (`EVALTRIM_NO_CACHE=1`, DF-capped blocking; same generator as v0.6):

| n | runtime_s | peak MiB | pairs | similarity_s | removal_s |
| --- | --- | --- | --- | --- | --- |
| 100 | 2.65 | 8.15 | 4950 | 2.50 | 0.09 |
| 500 | 11.51 | 72.0 | 19856 | 9.61 | 1.42 |
| 1000 | 19.44 | 100.9 | 27379 | 13.78 | 4.40 |
| 5000 | 133.38 | 257.1 | 59840 | 30.60 | 97.66 |
| 10000 | 436.84 | 408.6 | 76205 | 38.33 | 387.45 |

v0.6.0 5k was **249.3s** / 174694 pairs. 10k was not completed. Competitor runtime on this generator: **UNMEASURED**.

10k wall time is dominated by per-test counterfactual simulation (~387s), not pair scoring.

