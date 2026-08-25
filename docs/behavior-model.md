# Behavior model

A **behavior signature** is a normalized record:

- `domain` — refund, privacy, coding, shopping, …
- `action` — escalation, refusal, confirmation, execution, clarification, …
- `conditions` — atomic predicates (`amount_above_limit`, `ambiguous_request`, …)
- `state` — `normal`, `unauthenticated`, `error`, …
- `critical` — boolean

Coverage math uses **atoms**, for example:

```
domain:refund
action:escalation
condition:amount_above_limit
state:normal
flag:critical
```

## Extraction order

1. Explicit `tags` on the test (preferred, confidence 1.0).
2. Optional `BehaviorExtractor` if the user enabled an LLM adapter.
3. Deterministic keyword / amount heuristics on `input` + `expected`.

The default path never calls a network API. Repeated runs on the same text produce the same signature.

## Critical behaviors

Declare them at suite level:

```yaml
critical_behaviors:
  - destructive_action
  - payment
  - privacy
  - authentication
  - policy_violation
```

If a test is the only remaining witness for a declared name (or for a `critical: true` atom), EvalTrim will not recommend `RETIRE`. The recommendation is `KEEP`, or `REVIEW` when the oracle itself is conflicting and confidence is low — never silent deletion.
