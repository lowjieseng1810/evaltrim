"""Heuristic test-value score in [0, 100]. Not a statistical estimator."""

from __future__ import annotations

from evaltrim.models import Behavior, TestCase


def value_score(
    test: TestCase,
    behavior: Behavior,
    *,
    unique_atoms: list[str],
    total_atoms: int,
    max_cost: float,
) -> float:
    """
    Weighted heuristic:

      0.25 * criticality
      0.25 * uniqueness
      0.20 * historical failure signal
      0.15 * information (behavior richness)
      0.10 * change sensitivity (boundary / policy tags)
      0.05 * inverse execution cost

    Missing run stats contribute a small prior (0.15) rather than zeroing the term.
    """
    criticality = 1.0 if behavior.critical else 0.0
    uniqueness = min(1.0, len(unique_atoms) / max(1, min(total_atoms, 4)))
    stats = test.run_stats
    if stats and stats.runs > 0:
        failure_signal = min(1.0, (stats.failure_rate or 0.0) * 4.0 + (0.2 if stats.failures else 0.0))
    else:
        failure_signal = 0.15
    info = min(1.0, len(behavior.atoms()) / 8.0)
    sensitivity_tokens = {
        "amount_at_limit",
        "policy_boundary",
        "ambiguous_request",
        "confirmation_required",
        "destructive",
    }
    sensitivity = 1.0 if sensitivity_tokens & set(behavior.conditions) else 0.0
    cost = 0.0
    if stats and stats.estimated_cost_usd:
        cost = min(1.0, stats.estimated_cost_usd / max(max_cost, 1e-9))
    inverse_cost = 1.0 - cost
    raw = (
        0.25 * criticality
        + 0.25 * uniqueness
        + 0.20 * failure_signal
        + 0.15 * info
        + 0.10 * sensitivity
        + 0.05 * inverse_cost
    )
    return round(100.0 * raw, 2)
