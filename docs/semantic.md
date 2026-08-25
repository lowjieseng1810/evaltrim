# Semantic backends

1. **DEFAULT (offline)** — `normalize_text` (synonyms, light stemming, number words), lexical/n-gram, rare-token boosts, behavior Jaccard, expected-oracle TF-IDF, unique witnesses, counterfactual removal. Merge still requires high overlap **and** similar expected (see `analyze._decision`). Thresholds are not globally lowered.
2. **OPTIONAL EMBEDDING** — `HashingNgramEncoder` behind `EVALTRIM_EMBEDDINGS=1`. Mixes into the semantic channel. Still cannot RETIRE alone.
3. **OPTIONAL LLM** — interfaces in `evaltrim.llm`. Off by default. May use the network only when you enable it.

Hard negatives that share tokens but differ in behavior atoms (store credit vs plain refund) must not MERGE.
