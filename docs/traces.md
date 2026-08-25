# Traces

`evaltrim ingest-traces path.json|.jsonl` maps records into `NormalizedTrace`.

Supported event kinds (flexible input, stable internal fields):

- session, turn, model call, tool call, tool result, state transition, final output

Each event may include timestamp, model, provider, token usage, cost, latency, tool, arguments, result, trajectory position, provenance.

This is an ingestion schema, not a hosted tracing backend.
