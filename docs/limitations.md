# Limitations

- Semantic similarity is a local heuristic. Optional hashing embeddings are not a neural model. Some paraphrases are missed on purpose to protect hard negatives.
- Unique-witness and coverage math is over **declared/observed atoms in the suite**, not the unknown behavior space of the agent.
- Drift `LIKELY_SOURCE` is not causal attribution.
- Impacted-test selection is not a complete dependency graph.
- Suite health is a labeled heuristic, not a certification.
- Portfolio selection is greedy.
- Watch uses mtime polling; it is not an OS-specific recursive inotify daemon.
- `llm_judge` grader still skips unless you add a provider.
- EvalTrim never deletes or rewrites suite files.
- v0.5+ items (IDE, full MCP platform, self-healing, hosted SaaS) are not implemented. A tiny optional `mcp_adapter.dispatch` exists; it is not a server.
