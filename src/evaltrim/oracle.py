"""Oracle health heuristics. Not a proof of oracle correctness."""

from __future__ import annotations

from collections.abc import Sequence

from evaltrim.lifecycle import StaleStatus, stale_status
from evaltrim.models import Behavior, OracleConflict, OracleHealth, OracleStatus, TestCase


def analyze_oracles(
    tests: Sequence[TestCase],
    behaviors: Sequence[Behavior],
    *,
    stale_days: int = 180,
    semantic_pairs: list[tuple[str, str, float, float]] | None = None,
) -> tuple[list[OracleHealth], list[OracleConflict], set[str]]:
    """Return per-test health, conflict records, and ids biased to REVIEW (never RETIRE)."""
    beh = {t.id: b for t, b in zip(tests, behaviors, strict=True)}
    conflicts: list[OracleConflict] = []
    flagged: set[str] = set()

    for left, right, sem, exp in semantic_pairs or []:
        if sem >= 0.75 and exp <= 0.35:
            conflicts.append(
                OracleConflict(
                    left_id=left,
                    right_id=right,
                    kind="conflicting_expected",
                    detail="Similar inputs, dissimilar expected oracles.",
                )
            )
            flagged.update((left, right))
        lb, rb = beh[left], beh[right]
        if sem >= 0.7 and lb.critical != rb.critical:
            conflicts.append(
                OracleConflict(
                    left_id=left,
                    right_id=right,
                    kind="incompatible_criticality",
                    detail="Near-duplicate inputs disagree on criticality.",
                )
            )
            flagged.update((left, right))
        if sem >= 0.7 and lb.action != rb.action and lb.domain == rb.domain:
            conflicts.append(
                OracleConflict(
                    left_id=left,
                    right_id=right,
                    kind="region_policy_split",
                    detail="Same behavioral region encodes different actions.",
                )
            )
            flagged.update((left, right))
        if (
            sem >= 0.85
            and set(lb.conditions)
            and set(rb.conditions)
            and set(lb.conditions).isdisjoint(set(rb.conditions))
            and lb.action != rb.action
        ):
            conflicts.append(
                OracleConflict(
                    left_id=left,
                    right_id=right,
                    kind="contradictory_tags",
                    detail="Overlapping wording with disjoint behavior tags.",
                )
            )
            flagged.update((left, right))

    health: list[OracleHealth] = []
    for test in tests:
        reasons: list[str] = []
        status = OracleStatus.TRUSTED
        confidence = 0.8
        expected = test.expected.strip().lower()
        if len(expected) < 8 or expected in {"ok", "yes", "pass", "unknown", "tbd"}:
            status = OracleStatus.REVIEW
            confidence = 0.4
            reasons.append("Expected behavior is too short or placeholder-like.")
        if test.id in flagged:
            status = OracleStatus.CONFLICT
            confidence = min(confidence, 0.45)
            reasons.append("Participates in an oracle conflict pair.")
        ss = stale_status(test, stale_days=stale_days)
        if ss == StaleStatus.STALE:
            if status == OracleStatus.TRUSTED:
                status = OracleStatus.STALE
            reasons.append("Provenance or last-run age looks stale.")
            confidence = min(confidence, 0.7)
        if not reasons:
            reasons.append("No conflict heuristic fired; still a heuristic, not a proof.")
        health.append(OracleHealth(test_id=test.id, status=status, confidence=confidence, reasons=reasons))
    return health, conflicts, flagged
