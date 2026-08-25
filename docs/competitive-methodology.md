# Competitive methodology

Date of this verification pass: **2026-08-25**. EvalTrim **1.0.0**.

## Fairness

1. Each tool uses its normal API in an **isolated** tree (`/tmp/evaltrim-comp` or in-process AgentEval via `EVALTRIM_COMPETITOR_PATH`).
2. Competitors were not crippled. Missing extras are recorded; those graders were not scored.
3. EvalTrim has no hidden fixture-only flags.
4. Different names for the same check are compared on outcomes, not labels.
5. The same conceptual fixtures are used when both tools can consume the task (`fixtures/grader_cases.yaml`, `fixtures/common20.yaml`).
6. If reproduction failed: **UNMEASURED**. If the job differs: **NOT DIRECTLY COMPARABLE**. If the API does not exist: **Capability not offered**.
7. No fabricated competitor numbers. Catalog size is not detection quality.

## Isolated versions (this pass)

- AgentEval / agentevalkit **0.7.0**
- Promptfoo **0.122.0** on Node **v22.22.0** (echo provider; no share)
- DeepEval **4.2.0** ExactMatchMetric + PatternMatchMetric (GEval LLM-DEPENDENT)
- Inspect AI **0.3.260** mockllm + exact scorer
- EvalView **0.8.1** `compare_to_golden`
- AgentEvalHQ **0.28.0-beta** ResponseAssertions (dotnet 8.0.424)
- Vercel agent-eval: NOT DIRECTLY COMPARABLE
- Langfuse / Phoenix / Braintrust: NOT DIRECTLY COMPARABLE

## Unique witnesses

Coverage uniqueness requires counterfactual critical/requirement/boundary/history loss or an exclusive non-weak signature. Leftover generic bands (`amount_below_limit`) are anti-merge distinctive atoms, not suite unique witnesses. Ground truth in `benchmarks/*/benchmark_metadata.yaml` was not rewritten.

## Fairness

1. Each tool uses its normal API (EvalTrim `grade_record`; AgentEval `get_grader`).
2. Competitors were not crippled. Missing extras (`scipy`, `sentence-transformers`) are recorded; those graders were not scored.
3. EvalTrim has no hidden fixture-only flags.
4. Different names for the same check are compared on outcomes, not labels.
5. The same YAML fixtures are used when both tools can consume the task.
6. If reproduction failed: **UNMEASURED**. If the job differs: **NOT DIRECTLY COMPARABLE**. If the API does not exist: **Capability not offered**.
7. No fabricated competitor numbers.

## Tasks

`benchmarks/competitive/tasks/01_*.yaml` … `20_*.yaml` define input, expected behavior, metric, version, methodology, and pass/fail.

## AgentEval grader baseline

GitHub README (fetched 2026-08-25) documents **11** built-in graders including **trajectory**, LLM judge, JSON schema, semantic, latency, and cost:

https://github.com/agentkitai/agenteval/blob/main/README.md

PyPI **agentevalkit 0.7.0** ships **10** graders in `graders/__init__.py` and **no** `trajectory` module. The PyPI long description also says 10 graders. This verification scores the **installed wheel** and records the README delta.

Contains: AgentEval is case-sensitive; EvalTrim is case-insensitive. Regex: EvalTrim always IGNORECASE. Latency/cost missing values: EvalTrim skips; AgentEval fails. Those cases are excluded from common-subset accuracy.

## Statistics

EvalTrim `compare_samples`: Welch t-test, Cohen's d, practical thresholds. `regression_flag` needs statistical **and** practical significance **and** a mean decrease.

AgentEval `compare_runs`: Welch t-test; a statistically significant mean drop is `REGRESSED` at default threshold 0. The scipy extra was **not** installed; AgentEval used its pure-Python fallback.

## Red team

Common **quality** subset is EvalTrim local probes. Promptfoo **catalog breadth** is documented separately (157 plugins on public docs, 2026-08-25). Promptfoo CLI did not run on this host (Node `>=22.22.0` required by 0.122.0; host is 22.14.0; 0.120.0 drizzle migrator failed).

Do not compare catalog size to detection quality.

## Suite minimization

Constructed suites `coding`, `customer_support`, and `shopping` with immutable `benchmark_metadata.yaml`. Competitors that do not expose redundancy/witness/counterfactual APIs are **Capability not offered**, not scored as 0.

## Scores

A / B / C are means of EvalTrim fixture rates × 10.

- Unweighted overall = mean(A, B, C)
- Weighted variants: equal (1/3 each), intelligence heavier (0.3 / 0.3 / 0.4), eval+workflow heavier (0.4 / 0.4 / 0.2)
- Sensitivity = spread of those weighted totals

Competitor UNMEASURED cells are not filled with zeros.

## Status rule

**SUPERIOR** only if every directly comparable critical metric is equal or better, no critical safety metric is worse, no major DX/performance metric is worse where fairly measured, intelligence is measurably ahead, **and** major competitors are actually measured.

Incomplete data ⇒ **GAPS REMAIN** (also described as PARITY — INCOMPLETE HEAD-TO-HEAD DATA).
