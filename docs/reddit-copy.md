# Reddit copy — EvalTrim 1.0

Do not spam multiple subs on the same day. One technical post, then answer comments.

## Title

I built a local CLI that treats AI-agent eval suites like a coverage problem (unique witnesses + counterfactual removal)

## Body

Agent evals rot. You add paraphrases, a few “just in case” cases, then someone deletes what looked like a duplicate and you lose the only test for a privacy / payment boundary.

EvalTrim (MIT, Python, local-first) is an evaluation **control plane**: it grades/compares like a harness, but the point is **suite intelligence**.

Mechanism, short:

1. Normalize tests into behavior atoms.
2. Mark **unique witnesses** (exclusive coverage — not a rare token).
3. **Counterfactual removal**: simulate deleting a test and measure what coverage actually disappears.
4. Emit KEEP / MERGE / REVIEW / RETIRE with an evidence ledger. It never deletes the file.

Measured on constructed labeled suites (not production traffic): unique-witness P/R = 1.0, critical witness recall = 1.0, false critical witnesses = 0, retirement safety = 1.0. 10k synthetic cold analyze ≈ 54.7s on the machine we used.

Competitive claim is deliberately boring: **parity on the common eval dimensions we actually measured**, plus the suite-intelligence layer. Several competitor surfaces (10k scale, live red-team plugin catalogs, LLM judges, GUIs) stay UNMEASURED. I will not pretend those are wins.

Repo: https://github.com/lowjieseng1810/evaltrim

If you maintain a real agent eval YAML, I want failure cases more than stars.

## Comment reply templates

**“How is this not Promptfoo / Inspect / DeepEval?”**

Those are (mostly) runners and graders. EvalTrim can grade too, but the product is maintaining the *suite*: witnesses, counterfactual deletion, debt, portfolio. Complementary, not a replacement claim.

**“1.0 precision on your own benchmarks is meaningless.”**

Fair. They are constructed/labeled suites with frozen ground truth. We did not rewrite labels after scoring. If your production suite disagrees, that is the useful bug report.

**“Does it auto-delete tests?”**

No. Recommendations only.

**“Does it call OpenAI by default?”**

No. Default path is offline. LLM judge / embeddings are opt-in.
