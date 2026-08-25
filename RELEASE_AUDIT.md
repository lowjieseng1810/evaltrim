# EvalTrim 0.9.0 Release Audit

Version: **0.9.0** (not 1.0.0). Internal overall scorecard **8.92 / 10**. Competitive competitor metrics remain **UNMEASURED**.

| Gate | Result |
| --- | --- |
| pytest | 125 tests, pass |
| ruff check / format --check | clean |
| mypy | clean |
| python -m build | `evaltrim-0.9.0` sdist + wheel |
| constructed P/R/F1 | 1.0 / 1.0 / 1.0 on coding, customer_support, shopping |
| retirement safety / critical coverage | 1.0 / 1.0 |
| 10k scale | 56.75s, 409 MiB, 76205 pairs |

This is not a public “9/10 product” claim.
