# Competitive benchmark (Phase 0 audit)

EvalTrim 0.7 compares **developer-facing evaluation capabilities**, not SaaS dashboards, hosted traces, or marketing copy.

Rules used here:

- Measure EvalTrim in this repository.
- Do **not** invent competitor numbers.
- If a public implementation was not executed in this run, competitor status is **UNMEASURED** or **documented from public docs** (feature presence), not a scored win.
- If products are not the same job, mark **NOT DIRECTLY COMPARABLE**.

Sources consulted (public, 2026-08-25):

- EvalView — https://github.com/hidai25/eval-view and evalview.com (trajectory snapshots, GitHub Action, production monitor)
- AgentEval (`agentkitai/agenteval`) — YAML suites, graders including exact/contains/regex/json_schema/semantic/llm-judge/tool-check/trajectory/latency/cost, Welch regression, SQLite
- Vercel `agent-eval` — TypeScript coding-agent sandbox experiments (https://github.com/vercel-labs/agent-eval)
- AgentEvalHQ/AgentEval — public agent eval collection / harness (GitHub)
- Promptfoo — declarative evals, red team, CI
- DeepEval — pytest-style metrics including agent/tool/trajectory
- Inspect AI — UK AISI eval framework
- Langfuse, Arize Phoenix, Braintrust — experiment/observability platforms

## Capability matrix

| Capability | Competitor | Current competitor status | EvalTrim status | Gap | Target | Benchmark method | Evidence/source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A Evaluation breadth | AgentEval / Promptfoo / DeepEval | Public graders + suite runners | Local adapter runner + graders + intelligence | Close remaining grader types | Plugin graders covering listed types | `evaltrim run` + grader fixtures | This repo `evaluation/graders.py`; AgentEval README graders list |
| B Grader breadth | AgentEval (11 named graders) | Documented plugin-style YAML graders | Plugin registry: exact, contains, not_contains, regex, json/json_schema, semantic, llm_judge (opt-in skip), custom, tool_call, tool_args, trajectory (subsequence/lcs/strict), latency, ttft, tokens, cost | llm_judge still skip-by-default (intentional privacy) | Equal type coverage; LLM remains explicit | Count registered types; fixture pass/fail | AgentEval public grader names; EvalTrim `REGISTRY` |
| C Tool-call evaluation | AgentEval, DeepEval, langchain agentevals | Tool name/args/order matchers | `tool_call` + `tool_args` constraints | Arg equality was missing pre-0.7 | First-class arg constraints | Fixture: required/equals/forbidden | Public DeepEval tool correctness docs |
| D Trajectory evaluation | EvalView snapshots; AgentEval LCS; agentevals match modes | Snapshot diffs / LCS / set modes | Trajectory grader subsequence + LCS + strict | Snapshot *UX* of EvalView not cloned | Correctness of order constraints | LCS fixture | EvalView trajectory snapshot docs |
| E Multi-turn evaluation | EvalView, Vercel agent-eval, Promptfoo | Multi-turn / simulated users | `scenarios.Scenario` + trace session/turn | Persona catalogs less deep than Promptfoo red-team | Deterministic scenario replay | `replay_scenario` echo adapter | Promptfoo/EvalView docs |
| F Statistical evaluation | AgentEval Welch t-test | Documented Welch regression | Mean/median/var/stdev/percentiles/Wald CI/bootstrap CI/Welch/Cohen's d; statistical vs practical | False-regression tests | No flag on identical samples | `compare_samples` fixtures | AgentEval statistical regression docs |
| G Experiment management | Braintrust, Langfuse, Promptfoo | Hosted experiment UI **NOT DIRECTLY COMPARABLE** as a local CLI | Recorded-run compare, cache fingerprint, matrix, Pareto BEST_* | No hosted UI (intentional) | Local matrix + Pareto with evidence | `experiment-matrix` fixture | Braintrust/Langfuse product docs |
| H Result caching | Braintrust / Langfuse | Hosted caches **NOT DIRECTLY COMPARABLE** | SQLite KV + pair-score cache + experiment fingerprint | — | Deterministic reuse | cache hit on identical compare | EvalTrim `store.py` / `experiments.py` |
| I Replay | EvalView / Phoenix | Trace replay in products | `evaltrim run --record` + `replay` | Storage efficiency vs EvalView UNMEASURED | Deterministic re-grade | replay fixture | EvalView docs |
| J Regression detection | EvalView snapshots; AgentEval stats | Snapshot + statistical | UNCHANGED/EXPECTED/POSSIBLE/CONFIRMED/UNCERTAIN + channels | Provider errors were at risk of CONFIRMED | FP: provider error ≠ CONFIRMED | recorded-run fixtures | EvalView snapshot; AgentEval t-test |
| K Drift detection | Phoenix/Langfuse evaluations | Model/data drift in observability **partially NOT DIRECTLY COMPARABLE** | Model/provider/prompt/tool/schema/oracle/environment heuristics | Trend series less rich than Phoenix | Class + confidence, not causal proof | hash/model/provider fixtures | Phoenix tracing docs |
| L Trace normalization | Langfuse / Phoenix OTEL | Rich OTEL **NOT DIRECTLY COMPARABLE** as a tracing backend | Normalized session/turn/model/tool/state/output events | Not an OTEL collector | Round-trip JSON/JSONL | `ingest-traces` | Langfuse OTEL docs |
| M Production trace ingestion | EvalView incident→tests; Langfuse | Production monitors | `ingest-failure` + `compress-failures`; never auto-append | Compression measured internally | Families → unique witnesses | compression fixture | EvalView production monitor docs |
| N Flaky detection | CI tools / pytest plugins **NOT DIRECTLY COMPARABLE** as agent eval | STABLE/FLAKY/DEGRADED/ENVIRONMENTAL/QUARANTINED | Mis-classifying provider errors | ENVIRONMENTAL separate from FLAKY | outcome-sequence fixtures | — | |
| O Test generation | Promptfoo generators; EvalView incident tests | Generators / incident import | Boundary candidates + failure candidates; never auto-active | Weaker than dedicated generators | Candidate pipeline + portfolio | `ADD_CANDIDATE` never ACTIVE | Promptfoo generate docs |
| P Red-team / security | Promptfoo red team (catalog) | Large attack plugins | Modular family probes, not a copied catalog | Catalog **depth** UNMEASURED / likely behind Promptfoo | Interface + local detection fixtures | `evaltrim redteam` | Promptfoo red-team docs |
| Q Scenario evaluation | Promptfoo, Vercel agent-eval | Rich simulated users | Personas/styles + replay | Branching workflows limited | Reproducibility=1 on echo | `scenarios.py` | Vercel agent-eval README |
| R Sandbox support | Vercel agent-eval (coding sandbox) | **NOT DIRECTLY COMPARABLE** (cloud/coding sandbox) | Minimal local subprocess/fs/env/tool mocks | Not a VM | Escape-path test + documented limits | `LocalSandbox` | Vercel agent-eval |
| S CI integration | Promptfoo, EvalView, DeepEval | GitHub/CI examples | GitHub Action + `evaltrim check` / `gate` | — | Action present | `.github/workflows` | Public Actions |
| T GitHub integration | EvalView Action; Promptfoo | PR comments / actions | `--format github` PR comment + Action | Check-run API depth UNMEASURED | Comment body stable | rendered comment fixture | EvalView GH Action |
| U JSON API | Most CLIs | JSON outputs | Versioned `--format json` contract 1.0 | — | Extra keys allowed | `contract_version` | this repo `docs/json.md` |
| V Model comparison | Braintrust / Promptfoo | Experiment compare | Recorded cases + matrix | Live model sweep UNMEASURED (no keys by default) | Pareto BEST_QUALITY/COST/LATENCY | experiment-matrix fixture | Promptfoo view docs |
| W Cost tracking | AgentEval, Braintrust | Cost graders / traces | Usage.cost_usd + cost grader + experiment cost | Pricing tables not bundled | Recorded cost channels | cost grader fixture | AgentEval cost grader |
| X Latency / TTFT | AgentEval latency; provider APIs | Latency grader | latency + ttft graders + percentiles | TTFT only if recorded | skip if missing, fail if over | fixtures | AgentEval latency grader |
| Y Test selection | Generic CI selectors **NOT DIRECTLY COMPARABLE** | `watch` + `impacted-tests` + safety sample | Call-graph completeness | Precision/recall on labeled paths | impacted fixture | EvalTrim `impacted.py` |
| Z Test maintenance | Unique to EvalTrim vs most eval runners | KEEP/MERGE/RETIRE/REVIEW + evidence | Competitors rarely simulate removal | Keep conservative RETIRE | constructed safety=1.0 | `docs/benchmark.md` |
| AA Suite optimization | Rare in eval runners | Portfolio greedy+1-opt + Pareto sizes | Not MIQP-optimal | Critical witnesses retained | portfolio fixture | this repo |
| AB Behavior modeling | Rare | Behavior atoms + graph | — | Purity of deterministic classes | cluster fixture | this repo |
| AC Unique witnesses | Rare | Atoms/combos/boundaries/requirements/families | — | Precision/recall on constructed suites | benchmark metadata | this repo |
| AD Counterfactual removal | Rare | Indexed simulation, conservative verdicts | — | Safety 1.0 constructed | simulate-remove | this repo |
| AE Oracle reliability | Judge products **partially NOT DIRECTLY COMPARABLE** | Oracle health + human accept/reject metadata | Human labels optional | Do not treat judge confidence as accuracy | metadata reliability | this repo `oracle.py` / health |
| AF Evaluation debt | Rare | Actionable queues | — | Counts + kinds | `evaltrim debt` | this repo |
| AG Suite health | Rare | Component scores including cost_efficiency | Heuristic not certification | Sub-scores present | `evaltrim health` | this repo |
| AH Requirement coverage | Rare in generic evals | Requirement rows on suite | — | critical uncovered flagged | suite YAML requirements | this repo |
| AI Evidence / provenance | Braintrust scores **NOT DIRECTLY COMPARABLE** as hosted lineage | Proof graph on every recommendation | — | Export JSON/MD/GitHub | evidence ledger | this repo |
| AJ Portfolio optimization | Rare | Greedy + alternatives + Pareto budgets | — | Critical retained under max_tests | portfolio fixture | this repo |
| AK Incremental recomputation | Build systems **NOT DIRECTLY COMPARABLE** | Pair cache + suite fingerprint | — | Cache hit on unchanged suite | cache tests | this repo |
| AL Performance at scale | UNMEASURED vs others on same generator | Measured here: see results | 10k was incomplete in 0.6 | Complete 10k locally | `run_scale_benchmark` | this repo |
| AM Determinism | Inspect/Promptfoo vary with LLM | Offline path deterministic | LLM path not deterministic | Repeat analyze equal | constructed `deterministic` flag | this repo |
| AN Privacy / local-first | SaaS platforms require cloud **NOT DIRECTLY COMPARABLE** as hosted | No network by default | Optional LLM explicit | doctor network block | `docs/privacy.md` | this repo |
| AO Extensibility | Promptfoo/DeepEval plugins | `register_grader`, adapters, JSONL import | Not a plugin marketplace | Custom callable graders | plugin test | this repo |
| AP Developer experience | Varies | init → analyze → health JSON | Setup time UNMEASURED vs others | Minutes to first analysis | command count in README | this repo |

EvalView trajectory **snapshot developer UX** remains a peer strength; we grade trajectories but did not clone their Jest-like snapshot workflow. That UX is documented, not claimed beaten.

Vercel `agent-eval` sandbox depth is **NOT DIRECTLY COMPARABLE**.
