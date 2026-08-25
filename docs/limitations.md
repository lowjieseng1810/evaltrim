# Limitations

- Semantic similarity is local TF-IDF unless you add an embedding provider. Paraphrases can be missed or over-grouped.
- Behavior extraction is unambiguous when tags are present and heuristic otherwise. Ambiguous natural language will produce incomplete signatures.
- Oracle-conflict detection is a heuristic (similar inputs, dissimilar `expected`).
- A reduced suite is not a proof that every unknown production failure will still be caught.
- `RETIRE` / `MERGE` are review recommendations. Humans decide what to change in git.
- Optional LLM assistance can add non-determinism and privacy risk; leave it off for reproducible CI.
- Coverage is defined over **observed and declared atoms in the suite**, not over an unknown complete behavior space of the agent.
