# Architecture (v0.6)

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

v0.6 adds indexed removal, incremental pair cache, status/explain/gate/doctor, JSON for agents, SQLite history, and policy/error hardening.

