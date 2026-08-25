# Architecture (v0.4)

EvalTrim is a **suite** control plane, not an agent runtime.

```
suite / traces / failures
        │
        ▼
 behavior atoms ──► candidate pairs (layered retrieval)
        │                    │
        ▼                    ▼
 unique witnesses      semantic rerank
        │                    │
        └──────────┬─────────┘
                   ▼
        counterfactual removal
                   ▼
     KEEP / MERGE / RETIRE / REVIEW / ADD_CANDIDATE
                   │
                   ▼
            evidence ledger
```

Candidate pipeline:

1. Exact / hash dedup
2. Lexical normalization
3. Behavior blocking
4. TF / n-gram retrieval
5. Optional embedding retrieval
6. Semantic rerank
7. Unique-witness analysis
8. Counterfactual removal
9. Recommendation

Embeddings may create candidates. They never authorize RETIRE alone.

v0.3 adds a normalized trace schema, run comparison, likely-source drift labels, watch, impacted-test selection, flake history, and production-failure candidates.

v0.4 adds the behavior graph, compression ratio, health/debt, oracle/requirement reports, conflict graph, boundary candidates, greedy portfolio, and JSON evidence on every recommendation.
