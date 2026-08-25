# Evidence ledger, requirements, portfolio

Every recommendation includes JSON `evidence`:

- semantic_similarity
- behavior_overlap
- unique_witnesses_lost
- critical_coverage_lost
- requirement_coverage_lost
- historical_failure_contribution
- counterfactual_coverage_loss

Markdown reports print the same fields.

Requirements may be declared on the suite (`requirements:`) and referenced by `requirement_ids` on tests. Status: covered, partially_covered, uncovered, critical_uncovered.

`evaltrim portfolio SUITE --max-tests N --max-cost X --max-time-ms T` is a greedy selector that prefers unique critical witnesses. Alternatives are near-tie swaps, not a second solver.

`evaltrim ingest-failure failure.json SUITE` builds a candidate and scores uniqueness. It does not append the case.
