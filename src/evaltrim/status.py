"""evaltrim status — compact project summary for humans and coding agents."""

from __future__ import annotations

from typing import Any

from evaltrim.analyze import analyze_suite
from evaltrim.flake import classify_flake
from evaltrim.intelligence.debt import evaluation_debt
from evaltrim.intelligence.health import suite_health
from evaltrim.models import FlakeStatus, TestSuite
from evaltrim.store import recent_history


def project_status(suite: TestSuite) -> dict[str, Any]:
    result = analyze_suite(suite)
    health = suite_health(suite, result)
    debt = evaluation_debt(suite, result)
    flaky = []
    for test in suite.tests:
        status, _ = classify_flake(test)
        if status in {FlakeStatus.FLAKY, FlakeStatus.DEGRADED, FlakeStatus.QUARANTINED}:
            flaky.append(test.id)
    stale = [e.test_id for e in result.evidence if e.stale]
    regressions = recent_history("regression", limit=5)
    return {
        "project": suite.name or "unnamed-suite",
        "suite_size": len(suite.tests),
        "active_tests": result.summary.keep + result.summary.review,
        "recommendations": {
            "KEEP": result.summary.keep,
            "MERGE": result.summary.merge,
            "RETIRE": result.summary.retire,
            "REVIEW": result.summary.review,
        },
        "flaky": flaky,
        "stale": stale,
        "conflicts": list(result.conflicts),
        "critical_coverage": result.coverage.critical_coverage,
        "evaluation_debt": {"open_item_count": debt["open_item_count"]},
        "suite_health": {"composite": health["composite"], "heuristic": True},
        "recent_regressions": regressions,
        "note": "Status is local and heuristic. EvalTrim never deletes tests.",
    }
