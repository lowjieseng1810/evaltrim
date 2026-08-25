"""Recommendation policy. Destructive states are never silent."""

from __future__ import annotations

from evaltrim.models import (
    Recommendation,
    RecommendationState,
    RemovalSimulation,
    TestCase,
    Verdict,
)


def recommend(
    test: TestCase,
    *,
    unique_atoms: list[str],
    unique_critical: list[str],
    redundancy_max: float,
    merge_threshold: float,
    redundancy_threshold: float,
    simulation: RemovalSimulation,
    conflict: bool,
    stale: bool,
    low_confidence: bool,
    value_score: float,
) -> Recommendation:
    reasons: list[str] = []
    pair_ids: list[str] = []
    confidence = 0.85

    if unique_critical or simulation.lost_critical_atoms:
        reasons.append("Only meaningful witness for a critical behavior, or removal loses critical coverage.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.KEEP,
            reasons=reasons,
            value_score=value_score,
            confidence=0.99,
        )

    if conflict or low_confidence:
        if conflict:
            reasons.append("Semantically similar tests disagree on expected behavior (oracle conflict).")
        if low_confidence:
            reasons.append("Behavior extraction confidence is low or tags are incomplete.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.REVIEW,
            reasons=reasons,
            value_score=value_score,
            confidence=0.55,
        )

    unique_meaningful = [a for a in unique_atoms if not a.startswith("state:")]
    removal_safe = simulation.verdict == Verdict.SAFE_TO_RETIRE and not simulation.lost_atoms
    highly_redundant = redundancy_max >= merge_threshold
    redundant = redundancy_max >= redundancy_threshold

    if unique_meaningful:
        reasons.append(
            "Unique behavioral witness: " + ", ".join(_human_atom(a) for a in unique_meaningful[:6])
        )
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.KEEP,
            reasons=reasons,
            value_score=value_score,
            confidence=0.9,
        )

    if simulation.lost_atoms:
        reasons.append("Removal would drop behavior atoms: " + ", ".join(simulation.lost_atoms[:6]))
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.KEEP,
            reasons=reasons,
            value_score=value_score,
            confidence=0.88,
        )

    if highly_redundant and removal_safe and stale:
        reasons.append("Stale, highly redundant, and not a unique witness.")
        reasons.append(f"Max pair similarity {redundancy_max:.2f}; removal simulation is SAFE_TO_RETIRE.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.RETIRE,
            reasons=reasons,
            value_score=value_score,
            confidence=0.8,
            pair_ids=pair_ids,
        )

    if highly_redundant and removal_safe:
        reasons.append("Highly redundant with no unique behavioral contribution.")
        reasons.append("Prefer merging overlapping cases rather than deleting without review.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.MERGE,
            reasons=reasons,
            value_score=value_score,
            confidence=0.8,
        )

    if redundant and removal_safe and stale:
        reasons.append("Redundant and stale; no unique coverage. Review before retiring.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.RETIRE,
            reasons=reasons,
            value_score=value_score,
            confidence=0.7,
        )

    if redundant and not unique_meaningful:
        reasons.append("Overlaps other tests; keep unless a merge candidate is confirmed.")
        return Recommendation(
            test_id=test.id,
            state=RecommendationState.REVIEW,
            reasons=reasons,
            value_score=value_score,
            confidence=0.6,
        )

    reasons.append("No unique critical risk; retain as default unless maintainers choose otherwise.")
    return Recommendation(
        test_id=test.id,
        state=RecommendationState.KEEP,
        reasons=reasons,
        value_score=value_score,
        confidence=confidence,
    )


def _human_atom(atom: str) -> str:
    if ":" not in atom:
        return atom.replace("_", " ")
    kind, name = atom.split(":", 1)
    return f"{name.replace('_', ' ')} ({kind})"
