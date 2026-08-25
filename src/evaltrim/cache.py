"""Content-addressed analysis cache. Keys include algorithm version."""

from __future__ import annotations

import hashlib
import json
import os

from evaltrim.constants import ANALYSIS_ALGO_VERSION, CACHE_FORMAT_VERSION
from evaltrim.models import AnalysisResult, TestSuite
from evaltrim.simulate import SIMULATION_VERSION
from evaltrim.store import get_kv, put_kv


def cache_enabled() -> bool:
    flag = os.environ.get("EVALTRIM_NO_CACHE", "").lower()
    return flag not in {"1", "true", "yes"}


def suite_fingerprint(suite: TestSuite) -> str:
    payload = {
        "algo": ANALYSIS_ALGO_VERSION,
        "sim": SIMULATION_VERSION,
        "cache_format": CACHE_FORMAT_VERSION,
        "name": suite.name,
        "critical": list(suite.critical_behaviors),
        "requirements": [r.model_dump(mode="json") for r in suite.requirements],
        "config": suite.config.model_dump(mode="json"),
        "tests": [
            {
                "id": t.id,
                "input": t.input,
                "expected": t.expected,
                "tags": t.tags.model_dump(mode="json"),
                "requirement_ids": t.requirement_ids,
                "metadata": t.metadata,
                "run_stats": t.run_stats.model_dump(mode="json") if t.run_stats else None,
            }
            for t in suite.tests
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_cached_analysis(suite: TestSuite) -> AnalysisResult | None:
    if not cache_enabled():
        return None
    key = "analysis:" + suite_fingerprint(suite)
    try:
        blob = get_kv(key)
    except Exception:  # noqa: BLE001 — corrupt cache is a miss
        return None
    if not blob:
        return None
    try:
        return AnalysisResult.model_validate(blob)
    except Exception:  # noqa: BLE001
        return None


def store_cached_analysis(suite: TestSuite, result: AnalysisResult) -> None:
    if not cache_enabled():
        return
    key = "analysis:" + suite_fingerprint(suite)
    try:
        put_kv("analysis", key, json.loads(result.model_dump_json()))
    except Exception:  # noqa: BLE001
        return
