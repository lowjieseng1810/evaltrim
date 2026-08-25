# Competitive results

EvalTrim **0.9.0**. Benchmark date: 2026-08-25.

MEASURED competitor cells come from in-process AgentEval 0.7.0 on this machine. UNMEASURED means the tool was not successfully executed. NOT DIRECTLY COMPARABLE means hosted/UI or a different job. Do not treat UNMEASURED as an EvalTrim win.

**COMPETITIVE STATUS: GAPS REMAIN**

PARITY — INCOMPLETE HEAD-TO-HEAD DATA

On the AgentEval overlapping grader subset, accuracy tied at 1.0. That is not a superiority claim.

## Head-to-head table

| Capability | Metric | EvalTrim | AgentEval | Promptfoo | DeepEval | Inspect | EvalView | Vercel | Winner | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01_basic_grading | common_subset_accuracy | 1; MEASURED; v0.9.0 | 1; MEASURED; v0.7.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | TIE | fixtures/grader_cases.yaml; in-process; 2026-08-25; 4×Xeon 15GiB; AgentEval 0.7.0 |
| 02_json_schema | accuracy_on_three_gold_cases | 1; MEASURED; v0.9.0 | 1; MEASURED; v0.7.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | TIE | fixtures/grader_cases.yaml; in-process; 2026-08-25; 4×Xeon 15GiB; AgentEval 0.7.0; AgentEval uses jsonschema library |
| 03_tool_args | argument_equality | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | AgentEval 0.7.0 tool-check is names only |
| 04_trajectory | subsequence_accuracy | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | GitHub README lists trajectory; wheel 0.7.0 does not ship it |
| 05_multiturn | scenario_passed | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | NOT DIRECTLY COMPARABLE | UNMEASURED | examples/scenario_refund.yaml replay_scenario |
| 06_statistical_regression | false_regression_on_identical | 1; MEASURED; v0.9.0 | 1; MEASURED; v0.7.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | TIE | n=20 scores of 1.0 vs 1.0; EvalTrim compare_samples; AgentEval compare_runs |
| 06_statistical_regression | detect_mean_drop_1_to_0 | 1; MEASURED; v0.9.0 | 1; MEASURED; v0.7.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | TIE | Welch; methods documented in docs/competitive-methodology.md |
| 07_model_comparison | recorded_experiment_cache_hit | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | compare_experiments fingerprint KV; hosted experiment UIs NDC |
| 08_cache_reuse | cache_hit_rate_identical_compare | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | second compare_experiments call |
| 09_replay | replay_correctness | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | save_recording/replay_recording tempfile |
| 10_flaky_detection | four_class_accuracy | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | AgentEval binary is_flaky only |
| 10_flaky_detection | binary_mixed_accuracy | 1; MEASURED; v0.9.0; EvalTrim 4-class mapped to mixed vs stable | 1; MEASURED; v0.7.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | TIE | STABLE not flaky; others mixed. Mapping documented. |
| 11_drift_detection | provider_error_not_confirmed_regression | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | classify_run_delta; AgentEval has no provider-error class |
| 12_targeted_test_selection | provenance_recall_fixture | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | impacted_tests(['src/refund.py']) |
| 13_redteam | local_probe_detection_rate | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | evaltrim.security.evaluate_security; Promptfoo CLI not executed |
| 13_redteam | catalog_breadth | local family probes (not a plugin catalog) | UNMEASURED | 157 plugins DOCUMENTED (not CLI-counted) https://www.promptfoo.dev/docs/red-team/plugins/ | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | Catalog size ≠ detection quality on the common subset |
| 13_redteam | false_positives | 0; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | Lower is better; local probes only |
| 14_scenario | replayability | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | EchoExpectedAdapter scenario |
| 14_sandbox | isolation_level | LOCAL PROCESS SANDBOX (not container, not VM) | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | NOT DIRECTLY COMPARABLE | UNMEASURED | Do not equate subprocess sandbox with VM |
| 15_suite_minimization | redundancy_precision_min | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | constructed suites; immutable metadata |
| 15_suite_minimization | retirement_safety_min | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | false retirement must stay 0 on labeled criticals |
| 15_suite_minimization | critical_coverage_min | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | constructed suites |
| 16_unique_witness | unique_witness_precision_min | 0.8333; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | benchmark_metadata.yaml |
| 17_counterfactual_removal | false_retirement_rate_max | 0; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | lower is better; 0.0 on constructed |
| 18_portfolio_selection | critical_witness_retention_heuristic | 1; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | select_portfolio on demo suite |
| 19_failure_compression | families_from_three_records | 2; MEASURED; v0.9.0 | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | Capability not offered / not directly comparable | NOT DIRECTLY COMPARABLE | UNMEASURED | compress_production_failures; 2 families expected |
| 20_large_scale | runtime_same_generator | MEASURED (see scale table) | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | Competitors not run on generate_scale_suite |
| privacy_local_first | default_network_required | 0; MEASURED; v0.9.0; 0=no | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | NOT DIRECTLY COMPARABLE | UNMEASURED | EvalTrim default path has no network |
| mutation | constructed_mutation_score | 0.8571; MEASURED; v0.9.0 | Capability not offered / not directly comparable | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | evaltrim.intelligence.mutation |
| dx_runner | dry_run_and_smoke_and_parallel | 1; MEASURED; v0.9.0 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | run_suite dry_run/smoke/workers; competitor runner DX UNMEASURED |

## Scorecard (EvalTrim self-measurement; not a competitor deficit)

- A General Evaluation: **10.0 / 10**
- B Regression/Developer Workflow: **10.0 / 10**
- C Evaluation Intelligence: **9.5577 / 10**
- Overall unweighted mean: **9.8526 / 10**
- Weighted: `{'equal': 9.8526, 'intelligence_heavier': 9.8231, 'eval_workflow_heavier': 9.9115}`
- Weights: `{'equal': [0.3333333333333333, 0.3333333333333333, 0.3333333333333333], 'intelligence_heavier': [0.3, 0.3, 0.4], 'eval_workflow_heavier': [0.4, 0.4, 0.2]}`
- Sensitivity spread: 0.0885

Scores are EvalTrim self-measurements on fixtures (0–10). They are not a claim that competitors scored lower on UNMEASURED cells. AgentEval overlapping grader accuracy: 1.0.

## Scale (EvalTrim generator; competitors UNMEASURED)

These rows are measured **in the same process** as the rest of the harness (AgentEval imported), with `EVALTRIM_NO_CACHE=1` for the scale loop. Peak tracemalloc can still differ from a dedicated process in `docs/benchmark.md`. 
| n | runtime_s | peak MiB | pairs | simulations |
| --- | --- | --- | --- | --- |
| 100 | 5.8196 | 9.6 | 4950 | 1.0 |
| 500 | 11.6522 | 72.14 | 19856 | 1.0 |
| 1000 | 16.8477 | 101.06 | 27379 | 1.0 |
| 5000 | 40.1215 | 257.5 | 59840 | 1.0 |
| 10000 | 57.0143 | 409.17 | 76205 | 1.0 |

## Reproduction

Reproduced: ['agentevalkit==0.7.0']

Not reproducible: [{'name': 'promptfoo', 'attempted': ['0.122.0', '0.120.0'], 'reason': 'engine mismatch — CLI did not run'}, {'name': 'deepeval', 'reason': 'Not installed; no metrics fabricated'}, {'name': 'inspect_ai', 'reason': 'Not installed; no metrics fabricated'}, {'name': 'evalview', 'reason': 'Not installed; no metrics fabricated'}, {'name': 'vercel_agent_eval', 'reason': 'NOT DIRECTLY COMPARABLE'}, {'name': 'agentevalhq', 'reason': 'Not installed'}]

Hosted platforms: Langfuse / Phoenix / Braintrust = **NOT DIRECTLY COMPARABLE**.

