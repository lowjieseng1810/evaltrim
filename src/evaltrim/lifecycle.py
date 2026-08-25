"""Inferred test lifecycle. Authors may set metadata.lifecycle explicitly."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from evaltrim.models import TestCase


class Lifecycle(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    REVIEW = "REVIEW"
    AGING = "AGING"
    STALE = "STALE"
    QUARANTINED = "QUARANTINED"
    ARCHIVED = "ARCHIVED"


class StaleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    AGING = "AGING"
    STALE = "STALE"
    REVIEW = "REVIEW"


def explicit_lifecycle(test: TestCase) -> Lifecycle | None:
    raw = test.metadata.get("lifecycle")
    if not raw:
        return None
    try:
        return Lifecycle(str(raw).upper())
    except ValueError:
        return None


def stale_status(test: TestCase, *, stale_days: int = 180, aging_days: int = 90) -> StaleStatus:
    if test.metadata.get("quarantined") is True:
        return StaleStatus.REVIEW
    if test.metadata.get("stale") is True:
        return StaleStatus.STALE
    last = test.run_stats.last_run if test.run_stats else None
    created = test.created_at
    ref: datetime | None = last
    if ref is None and created:
        try:
            ref = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            ref = None
    if ref is None:
        return StaleStatus.ACTIVE
    now = datetime.now(ref.tzinfo or UTC)
    if ref.tzinfo is None:
        now = datetime.now(UTC).replace(tzinfo=None)
    age = (now - ref).days
    failures = test.run_stats.failures if test.run_stats else 0
    if age >= stale_days and not failures:
        return StaleStatus.STALE
    if age >= aging_days:
        return StaleStatus.AGING
    return StaleStatus.ACTIVE


def infer_lifecycle(
    test: TestCase,
    *,
    conflict: bool,
    stale_days: int = 180,
) -> Lifecycle:
    explicit = explicit_lifecycle(test)
    if explicit is not None:
        return explicit
    if test.metadata.get("archived") is True:
        return Lifecycle.ARCHIVED
    if test.metadata.get("quarantined") is True or conflict:
        return Lifecycle.QUARANTINED if test.metadata.get("quarantined") else Lifecycle.REVIEW
    status = stale_status(test, stale_days=stale_days)
    if status == StaleStatus.STALE:
        return Lifecycle.STALE
    if status == StaleStatus.AGING:
        return Lifecycle.AGING
    if test.metadata.get("draft") is True:
        return Lifecycle.DRAFT
    if test.metadata.get("validated") is True:
        return Lifecycle.VALIDATED
    return Lifecycle.ACTIVE
