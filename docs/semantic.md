# Semantic backends

Three tiers. Merge thresholds are **not** globally lowered. Behavioral evidence remains authoritative for KEEP / RETIRE.

1. **Tier 1 — cheap lexical (always)** — `normalize_text` (synonyms, light stemming, number words), Jaccard / TF cosine / n-grams, amount agreement, exception-clause penalty for hard negatives.
2. **Tier 2 — local hashing representation (always)** — `HashingNgramEncoder` mixed in at low weight. No network.
3. **Tier 3 — optional encoder or LLM comparator** — `EVALTRIM_EMBEDDINGS=1` or `EVALTRIM_LLM`. Off by default.

Each pair reports `semantic_confidence`, `behavior_confidence`, and `combined_confidence`. Combined confidence does not authorize RETIRE.

Hard negatives that share a request but add a contradicting clause (store credit vs plain refund) must not MERGE when behavior atoms differ.

See `tests/test_v09.py` for paraphrase vs hard-negative fixtures.
