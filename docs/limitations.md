# Limitations

- Semantic similarity is a local heuristic (tier 1–2). Optional hashing / LLM (tier 3) is not a hosted embedding API. Some paraphrases are missed on purpose to protect hard negatives.
- Unique-witness labels are over **declared/observed atoms and exclusive signatures**, not the unknown behavior space of the agent. Semantic matching never authorizes uniqueness.
- Trajectory compare is terminal/JSON/Markdown. EvalView’s snapshot/check UX was measured on canned `compare_to_golden` traces, not a live GUI.
- Competitor 10k-scale runs were not executed; those cells stay UNMEASURED.
- Drift `LIKELY_SOURCE` is not causal attribution.
- Impacted-test selection is not a complete dependency graph.
- Suite health is a labeled heuristic, not a certification.
- Portfolio selection is greedy. Named BEST_* portfolios are not proven mathematical optima.
- Watch uses mtime polling; it is not an OS-specific recursive inotify daemon.
- `llm_judge` grader still skips unless you add a provider callable.
- Local sandbox is **LOCAL SANDBOX**, not a SECURE ISOLATED VM / container / seccomp jail.
- Red-team probes are family-level fixtures, not a vendor attack catalog.
- Experiment compare uses recorded cases; there is no hosted experiment service.
- EvalTrim never deletes or rewrites suite files.
- Hosted SaaS, auto-delete, automatic repair, and a full MCP platform are out of scope.
