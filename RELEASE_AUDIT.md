# EvalTrim 1.0.0 Release Audit

Version: **1.0.0**. Competitive verification status: **VERIFIED PARITY ON MEASURED DIMENSIONS**.

This is not a claim of superiority on unmeasured or NOT OFFERED cells.

| Gate | Result |
| --- | --- |
| pytest | see latest run in this session |
| ruff / mypy / build | required before tag |
| unique witness (constructed + labeled) | precision/recall ≥ 0.95; critical witness recall 1.0; false critical 0 |
| retirement safety / critical coverage | 1.0 |
| red-team local probes | detection 1.0, FP 0 |
| 10k scale | must stay near the 0.9 ~57s band (cold cache) |
| competitors reproduced | AgentEval 0.7.0, Promptfoo 0.122.0, DeepEval 4.2.0, Inspect 0.3.260, EvalView 0.8.1, AgentEvalHQ 0.28.0-beta |

Historical 0.9.0 audit remains below for the freeze.

---

# EvalTrim 0.9.0 Release Audit

Version: **0.9.0** (not 1.0.0). Internal overall scorecard **8.92 / 10** (engineering self-assessment). Competitive verification status: **GAPS REMAIN**.
