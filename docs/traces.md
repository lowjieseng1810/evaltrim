# Traces

`evaltrim ingest-traces path.json|.jsonl` maps records into `NormalizedTrace`.

Compare two traces or step lists without a GUI:

```text
evaltrim replay --compare baseline.json candidate.json
```

Output is terminal Markdown (or `--format json`) with REMOVED STEP / NEW STEP, RISK, and recommended action.

Supported event kinds (flexible input, stable internal fields):

- session, turn, model call, tool call, tool result, state transition, final output

This is an ingestion schema, not a hosted tracing backend. Trajectory snapshot UX is CLI + JSON + Markdown, not a Jest-like GUI.


Supported event kinds (flexible input, stable internal fields):

- session, turn, model call, tool call, tool result, state transition, final output

Each event may include timestamp, model, provider, token usage, cost, latency, tool, arguments, result, trajectory position, provenance.

This is an ingestion schema, not a hosted tracing backend.
