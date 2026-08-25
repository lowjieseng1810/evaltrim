"""Flag missing boundary coverage. Generated cases are candidates, never auto-ACTIVE."""

from __future__ import annotations

from typing import Any

from evaltrim.boundary import classify_boundary
from evaltrim.models import TestSuite

INTERESTING = {
    "threshold_equality",
    "just_below_threshold",
    "just_above_threshold",
    "empty_input",
    "malformed_value",
    "missing_field",
}


def missing_boundary_candidates(suite: TestSuite) -> list[dict[str, Any]]:
    observed: set[str] = set()
    for test in suite.tests:
        observed.update(classify_boundary(test, limit=suite.config.policy_threshold))
    missing = sorted(INTERESTING - observed)
    out: list[dict[str, Any]] = []
    for mark in missing:
        out.append(
            {
                "kind": mark,
                "status": "ADD_CANDIDATE",
                "active": False,
                "suggestion": f"Add a candidate case covering boundary `{mark}`. Do not auto-activate.",
            }
        )
    return out
