"""Incremental pair scoring. Unchanged tests reuse persisted pair scores.

Coverage, unique witnesses, and removal still run on the current suite.
This only avoids re-scoring similarity for pairs whose content hashes match.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from evaltrim.cache import cache_enabled, suite_fingerprint
from evaltrim.constants import ANALYSIS_ALGO_VERSION
from evaltrim.models import TestCase, TestSuite
from evaltrim.store import get_kv, put_kv


def content_hash_for_test(test: TestCase) -> str:
    payload = {
        "id": test.id,
        "input": test.input,
        "expected": test.expected,
        "tags": test.tags.model_dump(mode="json"),
        "requirement_ids": test.requirement_ids,
        "metadata": test.metadata,
        "run_stats": test.run_stats.model_dump(mode="json") if test.run_stats else None,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pair_key(left: TestCase, right: TestCase) -> str:
    a, b = sorted(
        ((left.id, content_hash_for_test(left)), (right.id, content_hash_for_test(right))),
        key=lambda x: x[0],
    )
    return f"{a[0]}|{a[1]}|{b[0]}|{b[1]}"


class PairScoreCache:
    def __init__(self, stored: dict[str, Any]) -> None:
        self.stored = stored
        self.hits = 0
        self.misses = 0
        self._next: dict[str, Any] = {}

    @classmethod
    def load(cls, suite: TestSuite) -> PairScoreCache | None:
        if not cache_enabled():
            return None
        key = f"pairs:{ANALYSIS_ALGO_VERSION}:{suite.name or 'suite'}"
        try:
            blob = get_kv(key) or {}
        except Exception:  # noqa: BLE001
            blob = {}
        if not isinstance(blob, dict):
            blob = {}
        return cls(blob.get("pairs") or {})

    def get(self, left: TestCase, right: TestCase) -> dict[str, Any] | None:
        hit = self.stored.get(_pair_key(left, right))
        if hit is None:
            self.misses += 1
            return None
        self.hits += 1
        self._next[_pair_key(left, right)] = hit
        return dict(hit)

    def put(self, left: TestCase, right: TestCase, score: dict[str, Any]) -> None:
        self._next[_pair_key(left, right)] = score

    def save(self, suite: TestSuite) -> None:
        if not cache_enabled():
            return
        key = f"pairs:{ANALYSIS_ALGO_VERSION}:{suite.name or 'suite'}"
        try:
            put_kv(
                "pairs",
                key,
                {
                    "algo": ANALYSIS_ALGO_VERSION,
                    "suite_fp": suite_fingerprint(suite),
                    "pairs": self._next,
                },
            )
        except Exception:  # noqa: BLE001
            return


def changed_test_ids(previous_hashes: dict[str, str], suite: TestSuite) -> list[str]:
    current = {t.id: content_hash_for_test(t) for t in suite.tests}
    changed = [tid for tid, h in current.items() if previous_hashes.get(tid) != h]
    changed.extend(tid for tid in previous_hashes if tid not in current)
    return sorted(set(changed))
