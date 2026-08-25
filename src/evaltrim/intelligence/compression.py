"""Behavioral compression: coverage-preserving suite size, not deletion percentage."""

from __future__ import annotations

from typing import Any

from evaltrim.models import AnalysisResult, RecommendationState


def compression_stats(result: AnalysisResult) -> dict[str, Any]:
    n = result.summary.test_count or 1
    keep_like = sum(
        1
        for r in result.recommendations
        if r.state in {RecommendationState.KEEP, RecommendationState.REVIEW, RecommendationState.ADD_CANDIDATE}
    )
    unique_n = sum(1 for w in result.witnesses if w.unique_atoms or w.unique_critical or w.unique_boundary)
    active = max(keep_like, unique_n)
    original = n
    ratio = active / original if original else 1.0
    return {
        "original_tests": original,
        "meaningful_behavioral_witnesses": unique_n,
        "recommended_active_tests": active,
        "behavioral_compression_ratio": round(ratio, 4),
        "review_queue_merge_retire": result.summary.merge + result.summary.retire,
        "note": (
            "Compression measures remaining behavioral witnesses vs original count. "
            "It is not an automatic deletion percentage."
        ),
    }
