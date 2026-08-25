# EvalTrim

> Prove which AI-agent tests are worth keeping.

**Positioning (v0.2):** a local-first **evaluation control plane** — run and grade locally, then reason about whether the *evaluation suite* is healthy, redundant, or missing unique witnesses.

```
Run → Grade → Compare snapshots → Analyze suite intelligence → Maintain (recommendations only)
```

This is **not** a hosted observability product and **not** a drop-in replacement for Promptfoo, DeepEval, Inspect, Langfuse, Phoenix, or Braintrust. Those tools run and inspect evaluations. EvalTrim adds a layer that asks whether the tests themselves are worth keeping.

## Quick start

```bash
pip install -e ".[dev]"
evaltrim analyze examples/demo_suite.yaml
evaltrim run examples/demo_suite.yaml --agent echo-expected --dry-run
evaltrim import-jsonl examples/sample.jsonl -o /tmp/from-jsonl.json
evaltrim check examples/demo_suite.yaml --config examples/evaltrim.yaml
```

v0.1 commands still work: `validate`, `simulate-remove`, `maintain`, `benchmark`, `report`.

## What shipped in v0.2 (Phase A)

Implemented and tested:

- Canonical `EvaluationRecord` (`docs/canonical-manifest.md`)
- Local graders: exact, contains, regex, json, semantic, tool_call, trajectory, latency, cost; LLM judge is an explicit skip
- `evaltrim run` / `replay` with mock or subprocess adapters
- Snapshots under `.evaltrim/snapshots/` and `evaltrim compare` **of suites** (not live-agent verdicts)
- JSONL importer
- `evaltrim.yaml` policy checks (`docs/policies.md`)
- Normalized lexical similarity (paraphrase-aware tokens such as `$600` / “six hundred”) plus optional hashing embeddings (`EVALTRIM_EMBEDDINGS=1`)
- Blocking candidate generation for large suites

Not shipped (roadmap): hosted tracing, MCP, auto-deletion, self-healing, portfolio optimizer, watch mode.

## Measured suite-intelligence benchmarks

Source: `evaltrim benchmark benchmarks` on this repo. **No LLM. No embedding backend.** Version 0.2.0. Sizes are 12–14 tests per suite — not production scale.

Run the command locally for current numbers. Targets (not claims): redundancy precision ≥ 0.90; critical coverage preservation 1.0; 20–40% reduction on constructed suites.

## Privacy

Default: no network, no telemetry, cache dir `~/.cache/evaltrim` or `EVALTRIM_CACHE`. See [docs/privacy.md](docs/privacy.md).

## Limitations

See [docs/limitations.md](docs/limitations.md). Semantic similarity is heuristic. Coverage is over declared/observed atoms, not the unknown behavior space. Recommendations need human review.

## License

[MIT](LICENSE)
