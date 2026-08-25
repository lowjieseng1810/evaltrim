# Internal engineering scorecard (EvalTrim 0.9.0)

This file is an **internal** self-assessment. It is not a public rating, not a competitor benchmark, and not certification.

Scoring is 0–10 per core category. Target for this phase: no core category below 8.5 and overall ≥ 9.0. **This run did not claim that public marketing bar.**

## Scores

| Category | Score | Notes |
| --- | --- | --- |
| General evaluation | 9.2 | Plugin graders covering listed types; LLM judge still skip-by-default |
| Regression | 9.0 | UNCHANGED + provider-error ≠ CONFIRMED; recorded-run compare |
| Experiment | 8.7 | Verdicts + Pareto + manifests; still local/recorded, not a hosted experiment UI |
| Trace/replay | 8.8 | `replay --compare` terminal/JSON/MD diffs; not EvalView snapshot GUI |
| Red-team | 8.6 | Provider-neutral families + local detection 1.0 / FP 0; catalog depth still not Promptfoo |
| Scenario | 8.7 | Declarative YAML, personas, branch, state; echo replay only |
| Sandbox | 8.5 | LOCAL SANDBOX with escape tests; **not** a secure isolated VM |
| Performance | 9.3 | 10k 56.7s vs 436.8s in 0.7 on the same generator |
| Developer experience | 9.0 | init → analyze → doctor; richer doctor; compact reports |
| Privacy | 9.3 | No network by default; optional embeddings/LLM remain explicit |
| Evaluation intelligence | 9.2 | Witnesses, counterfactual, value components, info gain |
| Evidence | 9.1 | Stable node IDs; WHAT/WHY/EVIDENCE/RISK/ACTION cards |
| Suite optimization | 8.8 | Named greedy portfolios; explicitly not proven optima |
| GitHub/CI | 8.7 | Action + github comment format; check-run API still light |

**Overall (unweighted mean of 14): 8.92**

No core category is below 8.5. Overall is **below** 9.0, so the internal 9/10 target is **not** marked achieved.

## Why overall is not 9.0

The remaining drag is product-shape, not a single failing test:

- Experiment and trace UX are strong CLIs, not hosted consoles.
- Red-team is a local family framework, not a commercial attack catalog.
- Sandbox is honest about not being a VM.

Raising those to ≥9.5 would be a different phase (still not SaaS).

## Competitive labels (internal only)

Use Parity / Strong parity / Leading / Not comparable. Do not put these in marketing copy.

- Evaluation breadth: Strong parity (local CLI)
- Red-team catalog depth: Parity at interface, behind specialist catalogs
- Hosted experiment UI: Not comparable (intentional)
- Secure VM sandbox: Not comparable (LOCAL SANDBOX only)
- Eval suite maintenance / counterfactual removal: Leading among local eval CLIs we implement here (not a measured win vs unreproduced products)
