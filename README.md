# EvalTrim

> Prove which AI-agent tests are worth keeping.

1000 tests.  
Too expensive to run.  
Too messy to maintain.  
Too easy to accidentally delete the wrong one.

EvalTrim analyzes an **existing** AI-agent regression/eval suite and shows which tests are redundant, which uniquely protect behavior, and which can be retired **without weakening critical coverage**. Deletion is a recommendation. **Evidence is the product.**

## Illustrative example (not a measured result)

```
1000 tests
    ↓
281 redundant
    ↓
127 retirement candidates
    ↓
592 retained
    ↓
critical coverage: 100%
```

Those figures are a **storyboard**. Measured numbers come only from `evaltrim benchmark` on the suites in this repo (see [docs/benchmark.md](docs/benchmark.md)).

## Quick start

```bash
pip install .
# later: pip install evaltrim

evaltrim init
evaltrim analyze evals.yaml
evaltrim simulate-remove evals.yaml refund-001
evaltrim report evals.yaml --format markdown
evaltrim maintain evals.yaml
```

Run the bundled demo:

```bash
pip install -e ".[dev]"
chmod +x scripts/demo.sh
./scripts/demo.sh
```

Or:

```bash
evaltrim analyze examples/demo_suite.yaml
```

## What EvalTrim is not

It is **not** an observability platform, tracing backend, generic LLM judge, self-healing agent, prompt optimizer, or a replacement for your eval runner.

It works **with** existing test/eval artifacts (YAML or JSON). You keep running those tests however you already do.

## Where EvalTrim fits

Existing tools can run evals, inspect traces, compare experiments, and detect regressions.

EvalTrim focuses on:

- test redundancy (multi-factor, not embedding-threshold-only)
- unique behavioral witnesses
- coverage-preserving **removal simulation**
- evidence-backed suite maintenance reports (including GitHub PR comments)

## Input format

YAML or JSON, validated with Pydantic:

```yaml
critical_behaviors:
  - destructive_action
  - payment
  - privacy
  - authentication
  - policy_violation

tests:
  - id: refund-001
    input: "I want a refund of $600"
    expected: "Agent should escalate the request"
    tags:
      domain: refund
      action: escalation
      behavior:
        - amount_above_limit
        - escalation
      critical: true
    metadata:
      source: benchmark
      created_at: "2026-08-01"
    run_stats:          # optional
      runs: 40
      passes: 38
      failures: 2
      average_latency_ms: 1200
      estimated_cost_usd: 0.04
```

Run statistics are supplementary. Offline suites without history are fully supported.

## CLI

| Command | Purpose |
| --- | --- |
| `evaltrim init` | Write a starter `evals.yaml` |
| `evaltrim validate <suite>` | Schema check |
| `evaltrim analyze <suite>` | Coverage, redundancy, witnesses, recommendations |
| `evaltrim report <suite>` | Same analysis, report-oriented |
| `evaltrim simulate-remove <suite> <test_id>` | Virtual removal; never deletes files |
| `evaltrim maintain <suite>` | Writes `evaltrim-maintenance.md` (optional JSON) |
| `evaltrim benchmark [path]` | Score constructed suites vs ground truth |

`--format markdown|json|github` and `--output <path>` are supported on analysis commands.

`--strict` on `analyze` may fail (exit 3) if declared critical behaviors are uncovered or oracle conflicts are detected. Malformed suites fail with exit 2 regardless.

## How redundancy works

A pair score is **not** “embedding similarity > threshold”:

```
0.35 semantic  +  0.30 behavior overlap  +  0.20 expected similarity  +  0.15 historical overlap
```

Weights are configurable. A 0.94 score with distinct unique atoms still yields **KEEP BOTH**. Details: [docs/scoring.md](docs/scoring.md).

## Unique witnesses

For every test EvalTrim asks: *what behavior does this case uniquely prove?* If it is the only witness for a **critical** behavior, the recommendation is **KEEP**. If it proves nothing unique and is stale plus redundant, it may be **RETIRE** — still only as a review item.

## Removal simulation

```
BEFORE
Tests: 12
Behavior coverage: 100.0%
Critical coverage: 100.0%

AFTER removing refund-002b
Tests: 11
Behavior coverage: 100.0% -> 100.0%
Verdict: SAFE_TO_RETIRE
```

If the case is the only witness for destructive-action + privacy, the verdict is **KEEP**. See [docs/removal-simulation.md](docs/removal-simulation.md).

## Recommendation states

| State | Typical rule |
| --- | --- |
| KEEP | Unique (especially critical) witness, or removal loses coverage |
| MERGE | Highly redundant, no unique atoms, removal is coverage-safe |
| RETIRE | Stale **and** redundant **and** no unique coverage |
| REVIEW | Oracle conflict, low-confidence extraction, or ambiguous overlap |

EvalTrim will not recommend `RETIRE` for the only meaningful test of a critical behavior.

## GitHub Action

`.github/workflows/evaltrim.yml` installs the package, runs analysis, uploads a report artifact, and can comment on the PR. The job does **not** fail the build by default. Opt into `evaltrim analyze --strict`. See [docs/github-action.md](docs/github-action.md).

## Benchmark

```bash
evaltrim benchmark benchmarks
```

Suites: `benchmarks/customer_support`, `benchmarks/coding_agent`, `benchmarks/shopping_agent`. They include duplicates, near-duplicates, unique witnesses, boundaries, stale cases, critical cases, ambiguous wording, and conflicting expectations.

**Target** goals (not claims): redundancy precision ≥ 90%; critical coverage preservation 100%; 20–40% reduction on constructed suites; < 60s / 1000 cases without LLM; deterministic repeats. Compare against whatever the runner actually prints.

## Architecture

Local process, in-memory models, optional LLM interfaces that stay unused by default. Map: [docs/architecture.md](docs/architecture.md). Behavior atoms: [docs/behavior-model.md](docs/behavior-model.md).

## Privacy

No hosted backend, no telemetry, no automatic upload. LLM features are opt-in. [docs/privacy.md](docs/privacy.md).

## Limitations

Semantic similarity can miss paraphrases. Extraction can be ambiguous without tags. Oracle-drift detection is heuristic. A smaller suite does not guarantee catching every unknown failure. **Review recommendations before changing git.** Full list: [docs/limitations.md](docs/limitations.md).

## Roadmap (v0.2+)

- Importers for common eval JSONL / pytest layouts
- Optional embedding provider behind `SemanticComparator`
- HTML export (still no SaaS)
- Policy-as-code thresholds per repo

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
