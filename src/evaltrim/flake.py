"""Flaky-test history. Never automatically deletes a flaky case."""

from __future__ import annotations

from evaltrim.models import FlakeStatus, TestCase


def classify_flake(test: TestCase) -> tuple[FlakeStatus, dict[str, float | int | str]]:
    if test.quarantined or test.metadata.get("quarantined") is True:
        return FlakeStatus.QUARANTINED, {
            "runs": 0,
            "flake_rate": 0.0,
            "note": "Manually quarantined; never auto-deleted.",
        }
    outcomes = list(test.run_stats.outcomes) if test.run_stats else []
    if not outcomes and test.run_stats and test.run_stats.runs:
        # Reconstruct a coarse sequence from aggregate counts (not a true timeline).
        outcomes = ["pass"] * test.run_stats.passes + ["fail"] * test.run_stats.failures
    normalized = [o.lower() for o in outcomes]
    n = len(normalized)
    fails = sum(1 for o in normalized if o in {"fail", "failed", "error"})
    passes = sum(1 for o in normalized if o in {"pass", "passed", "ok"})
    flake_rate = fails / n if n else (test.run_stats.failure_rate or 0.0 if test.run_stats else 0.0)
    recent = normalized[-5:]
    recent_fails = sum(1 for o in recent if o in {"fail", "failed", "error"})
    if n >= 4 and recent and all(o in {"fail", "failed", "error"} for o in recent[-3:]) and passes > 0:
        status = FlakeStatus.DEGRADED
    elif 0.1 <= flake_rate <= 0.9 and n >= 4 and fails and passes:
        status = FlakeStatus.FLAKY
    else:
        status = FlakeStatus.STABLE
    return status, {
        "runs": n or (test.run_stats.runs if test.run_stats else 0),
        "passes": passes or (test.run_stats.passes if test.run_stats else 0),
        "failures": fails or (test.run_stats.failures if test.run_stats else 0),
        "flake_rate": round(float(flake_rate or 0.0), 4),
        "recent_fail_count": recent_fails,
        "status": status.value,
        "trend": "degrading"
        if status == FlakeStatus.DEGRADED
        else ("mixed" if status == FlakeStatus.FLAKY else "stable"),
    }


def flake_report(tests: list[TestCase]) -> list[dict]:
    rows = []
    for test in tests:
        status, detail = classify_flake(test)
        rows.append({"test_id": test.id, "status": status.value, **detail})
    return rows
