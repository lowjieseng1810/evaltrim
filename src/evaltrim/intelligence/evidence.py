"""Proof-carrying recommendation graph. Evidence, not causal proof."""

from __future__ import annotations

import hashlib
from typing import Any

from evaltrim.models import EvidenceLedger, OracleStatus, Recommendation, RemovalSimulation, TestCase


def evidence_node_id(*parts: str) -> str:
    raw = "|".join(parts)
    return "ev_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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
    steps = [
        ("input", True, test.input[:120]),
        ("behavior", True, test.behavior.label() if test.behavior else None),
        ("candidate_relation", True, rec.state.value),
        ("behavior_equivalence", overlap is not None, f"overlap={overlap}"),
        (
            "unique_witness_check",
            not unique or rec.state.value != "RETIRE",
            f"lost={simulation.lost_unique_witnesses}",
        ),
        (
            "requirement_check",
            not simulation.lost_requirement_ids or rec.state.value != "RETIRE",
            f"lost_requirements={simulation.lost_requirement_ids}",
        ),
        (
            "critical_check",
            not crit or rec.state.value != "RETIRE",
            f"critical_after={simulation.after_coverage.critical_coverage}",
        ),
        (
            "oracle_state",
            oracle_status != OracleStatus.CONFLICT if oracle_status else True,
            oracle_status.value if oracle_status else None,
        ),
        ("historical_value", True, f"failures={test.run_stats.failures if test.run_stats else 0}"),
        ("counterfactual", True, simulation.verdict.value),
        (
            "semantic_not_sufficient",
            True,
            f"semantic={semantic}; semantic never independently authorizes RETIRE",
        ),
        ("decision", True, rec.state.value),
    ]
    out = []
    for name, ok, detail in steps:
        node_id = evidence_node_id(test.id, name, str(detail))
        out.append({"id": node_id, "step": name, "ok": ok, "detail": detail})
    return out


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
    proof = proof_steps(
        rec,
        test=test,
        simulation=simulation,
        semantic=semantic,
        overlap=overlap,
        oracle_status=oracle_status,
    )
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
        proof=proof,
        information_gain=information_gain,
        failure_detection_value=failure_detection_value,
        nodes=proof,
    )


def render_evidence(ledger: EvidenceLedger, *, fmt: str = "markdown") -> str:
    if fmt == "json":
        import json

        return json.dumps(ledger.model_dump(mode="json"), indent=2)
    lines = [
        f"WHAT: {ledger.decision}",
        f"WHY: {ledger.notes[0] if ledger.notes else ledger.decision}",
        (
            "EVIDENCE: "
            f"behavior overlap {ledger.behavior_overlap} "
            f"unique witnesses lost {ledger.unique_witnesses_lost} "
            f"critical coverage loss {ledger.critical_coverage_lost} "
            f"historical failure contribution {ledger.historical_failure_contribution} "
            f"counterfactual loss {ledger.counterfactual_coverage_loss}"
        ),
        f"RISK: {'HIGH' if ledger.decision == 'KEEP' and ledger.unique_witnesses_lost else 'LOW'}",
        f"RECOMMENDED ACTION: {ledger.decision}",
    ]
    if fmt == "github":
        return "\n".join(lines)
    lines += ["", "Proof nodes:"]
    for node in ledger.nodes or ledger.proof:
        lines.append(f"- `{node.get('id')}` {node.get('step')}: {node.get('detail')}")
    return "\n".join(lines)
