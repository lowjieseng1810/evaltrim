# Product Hunt copy — EvalTrim 1.0

Keep claims factual. No “#1” / “world’s best.”

## Name

EvalTrim

## Tagline

Prove which AI-agent evals are worth keeping.

## Short description

A local-first evaluation control plane for AI agents. Find unique behavioral witnesses, simulate removing a test before you delete it, and get evidence-backed KEEP / MERGE / REVIEW recommendations.

## Long description

Agent eval suites rot the same way unit-test suites rot: paraphrases pile up, oracles go stale, and the one test that covered a critical behavior looks redundant until it is gone.

EvalTrim sits beside your harness. It records and grades runs, then maintains the evaluation system itself:

- Unique behavioral witnesses (not “rare tokens”)
- Counterfactual removal (what coverage disappears if this test is gone?)
- Suite health and evaluation debt (heuristics, not vanity scores)
- Portfolio selection under cost / time budgets
- Local-first: no hosted backend, no telemetry by default

1.0.0 is verified on constructed labeled suites (unique-witness precision/recall 1.0, critical witness recall 1.0, false critical witnesses 0, retirement safety 1.0). Those numbers are not production correctness. Competitive position is **parity on measured common eval dimensions**, plus suite intelligence competitors typically do not offer. Several competitor surfaces remain unmeasured.

MIT. Python CLI. GitHub: https://github.com/lowjieseng1810/evaltrim

## First comment

Thanks for looking at EvalTrim.

The bet is that evaluating the agent is only half the job. The eval suite itself needs witnesses, counterfactuals, and an evidence trail — otherwise “delete the duplicate” is a guess.

If you already run Promptfoo, Inspect, DeepEval, or an in-house harness, this is meant to sit next to them, not replace the runner.

I would rather hear “this recommendation is wrong on my suite” than a star with no repro. Link a YAML (redact prompts if needed) and I will look.

Maker: local-first, no account, no hosted backend.

## Suggested launch tags

developer-tools, artificial-intelligence, open-source, testing, productivity, github
