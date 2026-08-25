"""Human- and agent-readable explanations from stored evidence."""

from __future__ import annotations

from typing import Any

from evaltrim.analyze import analyze_suite
from evaltrim.errors import TestNotFoundError
from evaltrim.flake import classify_flake
from evaltrim.models import AnalysisResult, TestSuite


def explain_test(suite: TestSuite, test_id: str, *, result: AnalysisResult | None = None) -> dict[str, Any]:
    result = result or analyze_suite(suite)
    rec = next((r for r in result.recommendations if r.test_id == test_id), None)
    if rec is None:
        raise TestNotFoundError(f"Unknown test id: {test_id}")
    wit = next((w for w in result.witnesses if w.test_id == test_id), None)
    ev = next((e for e in result.evidence if e.test_id == test_id), None)
    test = suite.get(test_id)
    flake_status, flake_detail = classify_flake(test)
    others = [
        e.test_id
        for e in result.evidence
        if e.test_id != test_id and ev and set(e.behavior.atoms()) & set(ev.behavior.atoms())
    ]
    ledger = rec.evidence.model_dump(mode="json") if rec.evidence else {}
    return {
        "id": test_id,
        "kind": "test_recommendation",
        "verdict": rec.state.value,
        "unique_witness": (wit.unique_atoms + wit.unique_critical) if wit else [],
        "critical": bool(ev and ev.is_critical_witness),
        "other_tests_covering_same_behavior": others[:20],
        "other_tests_count": len(others),
        "removal_simulation": ledger.get("counterfactual_status"),
        "evidence": ledger,
        "reasons": rec.reasons,
        "flake": {"status": flake_status.value, **flake_detail},
        "oracle_status": ev.stale_status if ev else None,
        "conflict": bool(ev.conflict) if ev else False,
        "summary": _summary(rec.state.value, wit, ledger),
    }


def _summary(state: str, wit, ledger: dict[str, Any]) -> str:
    atoms = ", ".join((wit.unique_atoms[:6] if wit else []) or ["none"])
    return (
        f"WHY {state}\n"
        f"Unique witness: {atoms}\n"
        f"Critical coverage lost: {ledger.get('critical_coverage_lost')}\n"
        f"Counterfactual: {ledger.get('counterfactual_status')}\n"
        f"Verdict: {state}"
    )
