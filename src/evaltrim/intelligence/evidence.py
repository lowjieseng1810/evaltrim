"""Structured evidence attached to every recommendation."""

from __future__ import annotations

from evaltrim.models import EvidenceLedger, OracleStatus, Recommendation, RemovalSimulation, TestCase


def ledger_for(
    rec: Recommendation,
    *,
    test: TestCase,
    simulation: RemovalSimulation,
    semantic: float | None,
    overlap: float | None,
    oracle_status: OracleStatus | None,
) -> EvidenceLedger:
    hist = 0.0
    if test.run_stats and test.run_stats.failures:
        hist = float(test.run_stats.failures)
    drop = simulation.before_coverage.behavior_coverage - simulation.after_coverage.behavior_coverage
    crit_drop = simulation.before_coverage.critical_coverage - simulation.after_coverage.critical_coverage
    return EvidenceLedger(
        decision=rec.state.value,
        semantic_similarity=semantic,
        behavior_overlap=overlap,
        unique_witnesses_lost=len(simulation.lost_unique_witnesses),
        critical_coverage_lost=round(max(0.0, crit_drop), 6),
        requirement_coverage_lost=len(simulation.lost_requirement_ids),
        historical_failure_contribution=hist,
        counterfactual_coverage_loss=round(max(0.0, drop), 6),
        counterfactual_status=simulation.verdict.value,
        oracle_status=oracle_status.value if oracle_status else None,
        notes=list(rec.reasons),
    )
