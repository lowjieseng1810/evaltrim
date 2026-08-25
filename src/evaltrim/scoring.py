"""Heuristic test-value score in [0, 100]. Not a statistical estimator.

Every component is returned separately so the score is never a black box.
"""

from __future__ import annotations

from evaltrim.models import Behavior, TestCase, ValueWeights


def value_components(
    test: TestCase,
    behavior: Behavior,
    *,
    unique_atoms: list[str],
    total_atoms: int,
    max_cost: float,
    weights: ValueWeights | None = None,
    requirement_n: int = 0,
    oracle_confidence: float = 1.0,
) -> dict[str, float]:
    weights = weights or ValueWeights()
    uniqueness = min(1.0, len(unique_atoms) / max(1, min(total_atoms, 4)))
    criticality = 1.0 if behavior.critical else 0.0
    info = min(1.0, (len(behavior.atoms()) + len(unique_atoms)) / 10.0)
    stats = test.run_stats
    if stats and stats.runs > 0:
        failure_signal = min(1.0, (stats.failure_rate or 0.0) * 4.0 + (0.2 if stats.failures else 0.0))
        flake = 1.0 if 0.15 < (stats.failure_rate or 0.0) < 0.85 and stats.runs >= 3 else 0.0
        cost = min(1.0, (stats.estimated_cost_usd or 0.0) / max(max_cost, 1e-9))
    else:
        failure_signal = 0.15
        flake = 0.0
        cost = 0.0
    req = min(1.0, requirement_n / 2.0)
    sensitivity_tokens = {
        "amount_at_limit",
        "policy_boundary",
        "ambiguous_request",
        "confirmation_required",
        "destructive",
    }
    boundary = 1.0 if sensitivity_tokens & set(behavior.conditions) else 0.0
    return {
        "uniqueness": round(uniqueness, 4),
        "criticality": round(criticality, 4),
        "information_gain": round(info, 4),
        "historical_failures": round(failure_signal, 4),
        "requirement_coverage": round(req, 4),
        "boundary": round(boundary, 4),
        "inverse_cost": round(1.0 - cost, 4),
        "inverse_flakiness": round(1.0 - flake, 4),
        "oracle_confidence": round(max(0.0, min(1.0, oracle_confidence)), 4),
    }


def value_score(
    test: TestCase,
    behavior: Behavior,
    *,
    unique_atoms: list[str],
    total_atoms: int,
    max_cost: float,
    weights: ValueWeights | None = None,
    requirement_n: int = 0,
    oracle_confidence: float = 1.0,
) -> float:
    weights = weights or ValueWeights()
    parts = value_components(
        test,
        behavior,
        unique_atoms=unique_atoms,
        total_atoms=total_atoms,
        max_cost=max_cost,
        weights=weights,
        requirement_n=requirement_n,
        oracle_confidence=oracle_confidence,
    )
    raw = (
        weights.uniqueness * float(parts["uniqueness"])
        + weights.criticality * float(parts["criticality"])
        + weights.information_gain * float(parts["information_gain"])
        + weights.historical_failures * float(parts["historical_failures"])
        + weights.requirement_coverage * float(parts["requirement_coverage"])
        + weights.boundary * float(parts["boundary"])
        + weights.inverse_cost * float(parts["inverse_cost"])
        + weights.inverse_flakiness * float(parts["inverse_flakiness"])
        + weights.oracle_confidence * float(parts["oracle_confidence"])
    )
    return round(100.0 * raw, 2)
