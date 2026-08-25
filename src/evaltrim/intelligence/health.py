"""Heuristic suite health. Not a certification score."""

from __future__ import annotations

from typing import Any

from evaltrim.flake import classify_flake
from evaltrim.models import AnalysisResult, FlakeStatus, OracleStatus, TestSuite


def suite_health(suite: TestSuite, result: AnalysisResult) -> dict[str, Any]:
    n = max(len(suite.tests), 1)
    stale_frac = sum(1 for e in result.evidence if e.stale) / n
    tagged = sum(1 for t in suite.tests if t.tags.domain or t.tags.action or t.tags.behavior) / n
    provenanced = sum(1 for t in suite.tests if t.source or t.provenance_files) / n
    trusted = sum(1 for h in result.oracle_health if h.status == OracleStatus.TRUSTED) / max(
        len(result.oracle_health) or n, 1
    )
    conflict_frac = len(result.conflicts) / n
    redundant_frac = (result.summary.merge + result.summary.retire) / n
    unique_frac = sum(1 for w in result.witnesses if w.unique_atoms) / n
    flaky_n = 0
    for test in suite.tests:
        status, _ = classify_flake(test)
        if status in {FlakeStatus.FLAKY, FlakeStatus.DEGRADED, FlakeStatus.QUARANTINED}:
            flaky_n += 1
    flaky_frac = flaky_n / n

    coverage = round(result.coverage.behavior_coverage * 100, 1)
    critical = round(result.coverage.critical_coverage * 100, 1)
    redundancy = round(max(0.0, 100.0 - redundant_frac * 100), 1)
    diversity = round(min(100.0, unique_frac * 200), 1)
    freshness = round(max(0.0, 100.0 - stale_frac * 100), 1)
    flakiness = round(max(0.0, 100.0 - flaky_frac * 100), 1)
    oracle = round(trusted * 100, 1)
    conflicts = round(max(0.0, 100.0 - conflict_frac * 200), 1)
    provenance = round(provenanced * 100, 1)
    maintainability = round((tagged * 50 + (1 - stale_frac) * 25 + (1 - conflict_frac) * 25) * 100 / 100, 1)

    components = {
        "coverage": coverage,
        "critical_coverage": critical,
        "redundancy": redundancy,
        "diversity": diversity,
        "freshness": freshness,
        "flakiness": flakiness,
        "oracle_health": oracle,
        "conflicts": conflicts,
        "provenance": provenance,
        "maintainability": maintainability,
    }
    weights = {
        "coverage": 0.12,
        "critical_coverage": 0.18,
        "redundancy": 0.08,
        "diversity": 0.10,
        "freshness": 0.08,
        "flakiness": 0.08,
        "oracle_health": 0.12,
        "conflicts": 0.10,
        "provenance": 0.07,
        "maintainability": 0.07,
    }
    composite = round(sum(components[k] * weights[k] for k in components), 1)
    return {
        "heuristic": True,
        "composite": composite,
        "components": components,
        "note": (
            "Suite health is a local heuristic for maintainers. It is not a statistical guarantee of agent quality."
        ),
    }
