"""Historical failure-detection value. Uses recorded history when present."""

from __future__ import annotations

from typing import Any

from evaltrim.models import AnalysisResult, TestSuite


def failure_detection_value(suite: TestSuite, result: AnalysisResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_w = {w.test_id: w for w in result.witnesses}
    fail_ids = [t.id for t in suite.tests if t.run_stats and t.run_stats.failures]
    unique_fail = set(fail_ids) if len(fail_ids) == 1 else {t.id for t in suite.tests if by_w[t.id].unique_failure}
    for test in suite.tests:
        stats = test.run_stats
        failures = stats.failures if stats else 0
        unique = test.id in unique_fail
        crit = bool(by_w[test.id].unique_critical)
        value = 0.0
        if unique and crit:
            value += 50
        elif unique:
            value += 25
        value += min(25.0, float(failures) * 2)
        if by_w[test.id].unique_failure_family:
            value += 15
        rows.append(
            {
                "test_id": test.id,
                "failure_detection_value": round(value, 2),
                "failures_uniquely_caught": unique,
                "critical_failures_uniquely_caught": unique and crit,
                "historical_failures": failures,
                "note": "Value uses suite history. Missing history is not treated as zero unique detections.",
            }
        )

    def _rank(row: dict[str, Any]) -> tuple[float, str]:
        score = row["failure_detection_value"]
        assert isinstance(score, float)
        return (-score, str(row["test_id"]))

    rows.sort(key=_rank)
    return rows
