"""Evaluator conflict graph: same behavior region, incompatible oracles."""

from __future__ import annotations

from typing import Any

from evaltrim.models import AnalysisResult, RecommendationState


def evaluator_conflict_graph(result: AnalysisResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for conflict in result.oracle_conflicts:
        key = tuple(sorted((conflict.left_id, conflict.right_id)))
        typed = (key[0], key[1])
        if typed in seen:
            continue
        seen.add(typed)
        rows.append(
            {
                "left_id": conflict.left_id,
                "right_id": conflict.right_id,
                "kind": conflict.kind,
                "detail": conflict.detail,
                "status": "CONFLICT",
                "required": RecommendationState.REVIEW.value,
            }
        )
    return rows
