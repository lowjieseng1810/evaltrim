# Benchmark taxonomy (A–AP)

Each row is a capability. Where a fair numeric comparison exists, the method is listed. Otherwise: **NOT DIRECTLY COMPARABLE**.

| ID | Capability | Measurable benchmark | Notes |
| --- | --- | --- | --- |
| A | Evaluation breadth | Count of first-class eval surfaces (run, grade, record, replay) | Presence is weak; prefer correctness fixtures |
| B | Grader breadth | Registered grader types; fixture pass/fail per type | LLM judge skip-by-default is a privacy choice |
| C | Tool-call evaluation | Precision of required/forbidden/arg constraints | Local fixtures |
| D | Trajectory evaluation | Subsequence / LCS / strict match correctness | Not EvalView snapshot UX |
| E | Multi-turn evaluation | Scenario replay reproducibility on echo adapter | Live agents vary |
| F | Statistical evaluation | False regression rate on identical samples; detection of planted mean shift | Welch + practical vs statistical |
| G | Experiment management | Matrix + Pareto labels with recorded metrics | Hosted UIs NDC |
| H | Result caching | Cache hit on identical experiment fingerprint | |
| I | Replay | Re-grade equality vs recording; wall time; JSON size | |
| J | Regression detection | FP/FN on labeled recorded-run pairs | Provider errors must not be CONFIRMED |
| K | Drift detection | Attribution accuracy on labeled hash/model/oracle changes | Heuristic, not causal |
| L | Trace normalization | Round-trip required fields present | Not OTEL backend |
| M | Production ingestion | Compression ratio families/witnesses; never auto-insert | |
| N | Flaky detection | Classification accuracy on labeled sequences | ENVIRONMENTAL vs FLAKY |
| O | Test generation | Acceptance rate / redundancy of generated candidates | Generated ≠ active |
| P | Red-team | Family coverage, detection rate, FP, reproducibility | Not a vendor catalog |
| Q | Scenarios | Replay reproducibility | |
| R | Sandbox | Path-escape rejection; mock tool call | Not a cloud VM |
| S | CI | Workflow present; `check` exit codes | |
| T | GitHub | Comment renderer nonempty | Check-run API NDC |
| U | JSON contract | `contract_version` on commands | |
| V | Model comparison | BEST_* keys from recorded matrix | |
| W | Cost tracking | Cost grader + experiment cost | |
| X | Latency / TTFT | Percentiles + graders | Missing TTFT → skip |
| Y | Test selection | Precision/recall on labeled provenance paths; execution reduction | |
| Z | Test maintenance | Retirement safety; false RETIRE on unique critical | |
| AA | Suite optimization | Coverage retained vs size | |
| AB | Behavior modeling | Class purity/stability (deterministic partition) | |
| AC | Unique witnesses | Precision/recall vs metadata | |
| AD | Counterfactual removal | Safety 1.0 on constructed criticals | |
| AE | Oracle reliability | Human accept/reject when labeled; else heuristic health | Confidence ≠ accuracy |
| AF | Evaluation debt | Actionable kind counts | |
| AG | Suite health | Component keys present | Heuristic |
| AH | Requirement coverage | Uncovered critical requirements | |
| AI | Evidence | Proof steps on recommendations | |
| AJ | Portfolio | Critical witness retained under budget | |
| AK | Incremental | Pair-cache hits | |
| AL | Scale | Wall time / peak MiB / pairs for n=100…10000 | Vs competitors UNMEASURED unless reproduced |
| AM | Determinism | Two analyzes equal offline | |
| AN | Privacy | Default network requirements = none | |
| AO | Extensibility | Custom grader registration | |
| AP | DX | Commands to first useful JSON | Competitor install times UNMEASURED |
