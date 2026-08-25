# EvalTrim 0.9.0 Release Audit

Version: **0.9.0** (not 1.0.0). Internal overall scorecard **8.92 / 10** (engineering self-assessment). Competitive verification status: **GAPS REMAIN**.

| Gate | Result |
| --- | --- |
| pytest | pass (`tests/`, including competitive harness) |
| ruff check / format --check | clean |
| mypy | clean |
| python -m build | `evaltrim-0.9.0` sdist + wheel |
| constructed P/R/F1 | 1.0 / 1.0 / 1.0 on coding, customer_support, shopping |
| retirement safety / critical coverage | 1.0 / 1.0 |
| AgentEval 0.7.0 grader common-subset accuracy | TIE 1.0 vs 1.0 (MEASURED) |
| Promptfoo / DeepEval / Inspect / EvalView | UNMEASURED (not reproduced) |

Dedicated 10k scale remains documented in `docs/benchmark.md` (`EVALTRIM_NO_CACHE=1`). In-process competitive-harness scale is reported separately and is not a replacement for that isolation.

This is not a public “9/10 product” claim. Unmeasured competitor cells are not wins.
