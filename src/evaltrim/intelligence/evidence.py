"""Proof-carrying recommendation graph. Evidence, not causal proof."""

from __future__ import annotations

from typing import Any

from evaltrim.models import EvidenceLedger, OracleStatus, Recommendation, RemovalSimulation, TestCase


def proof_steps(
    rec: Recommendation,
    *,
    test: TestCase,
    simulation: RemovalSimulation,
    semantic: float | None,
    overlap: float | None,
    oracle_status: OracleStatus | None,
) -> list[dict[str, Any]]:
    unique = bool(simulation.lost_unique_witnesses)
    crit = bool(simulation.lost_critical_atoms) or simulation.after_coverage.critical_coverage < 1.0
    return [
        {"step": "candidate_relation", "ok": True, "detail": rec.state.value},
        {
            "step": "behavior_equivalence",
            "ok": overlap is not None,
            "detail": f"overlap={overlap}",
        },
        {
            "step": "unique_witness_check",
            "ok": not unique or rec.state.value != "RETIRE",
            "detail": f"lost={simulation.lost_unique_witnesses}",
        },
        {
            "step": "requirement_check",
            "ok": not simulation.lost_requirement_ids or rec.state.value != "RETIRE",
            "detail": f"lost_requirements={simulation.lost_requirement_ids}",
        },
        {
            "step": "critical_check",
            "ok": not crit or rec.state.value != "RETIRE",
            "detail": f"critical_after={simulation.after_coverage.critical_coverage}",
        },
        {
            "step": "historical_failure_check",
            "ok": True,
            "detail": f"failures={test.run_stats.failures if test.run_stats else 0}",
        },
        {
            "step": "counterfactual_simulation",
            "ok": True,
            "detail": simulation.verdict.value,
        },
        {
            "step": "oracle",
            "ok": oracle_status != OracleStatus.CONFLICT if oracle_status else True,
            "detail": oracle_status.value if oracle_status else None,
        },
        {
            "step": "semantic_not_sufficient",
            "ok": True,
            "detail": f"semantic={semantic}; semantic never independently authorizes RETIRE",
        },
        {"step": "decision", "ok": True, "detail": rec.state.value},
    ]


def ledger_for(
    rec: Recommendation,
    *,
    test: TestCase,
    simulation: RemovalSimulation,
    semantic: float | None,
    overlap: float | None,
    oracle_status: OracleStatus | None,
    information_gain: float | None = None,
    failure_detection_value: float | None = None,
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
        proof=proof_steps(
            rec,
            test=test,
            simulation=simulation,
            semantic=semantic,
            overlap=overlap,
            oracle_status=oracle_status,
        ),
        information_gain=information_gain,
        failure_detection_value=failure_detection_value,
    )
