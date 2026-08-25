"""Evaluation debt inventory. Never auto-deletes tests."""

from __future__ import annotations

from typing import Any

from evaltrim.flake import classify_flake
from evaltrim.models import AnalysisResult, FlakeStatus, RecommendationState, TestSuite


def evaluation_debt(suite: TestSuite, result: AnalysisResult) -> dict[str, Any]:
    rec = {r.test_id: r for r in result.recommendations}
    stale = [e.test_id for e in result.evidence if e.stale]
    merge_or_retire = {RecommendationState.MERGE, RecommendationState.RETIRE}
    redundant = [r.test_id for r in result.recommendations if r.state in merge_or_retire]
    low_value = [
        r.test_id for r in result.recommendations if r.value_score < 20 and r.state != RecommendationState.KEEP
    ]
    flaky: list[str] = []
    quarantined: list[str] = []
    for test in suite.tests:
        status, _ = classify_flake(test)
        if status == FlakeStatus.QUARANTINED:
            quarantined.append(test.id)
        elif status in {FlakeStatus.FLAKY, FlakeStatus.DEGRADED}:
            flaky.append(test.id)
    conflicts = list(result.conflicts)
    uncovered = [row.requirement_id for row in result.requirement_coverage if row.uncovered]
    missing_prov = [t.id for t in suite.tests if not t.source and not t.provenance_files]
    uncertain = [
        r.test_id for r in result.recommendations if r.state == RecommendationState.REVIEW or (r.confidence < 0.6)
    ]
    items = [
        {"kind": "stale_tests", "ids": stale},
        {"kind": "redundant_tests", "ids": redundant},
        {"kind": "low_value_tests", "ids": low_value},
        {"kind": "flaky_tests", "ids": flaky},
        {"kind": "quarantined_tests", "ids": quarantined},
        {"kind": "conflicts", "ids": conflicts},
        {"kind": "uncovered_requirements", "ids": uncovered},
        {"kind": "missing_provenance", "ids": missing_prov},
        {"kind": "uncertainty", "ids": uncertain},
    ]
    total = sum(len(x["ids"]) for x in items)
    return {
        "title": "Evaluation Debt Report",
        "items": items,
        "open_item_count": total,
        "note": "Debt items are review queues. Flaky tests are never deleted automatically.",
        "recommendations": {tid: rec[tid].state.value for tid in rec},
    }
