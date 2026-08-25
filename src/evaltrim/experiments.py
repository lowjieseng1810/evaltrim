"""Deterministic experiment / model / prompt / tool comparison with result reuse."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from evaltrim.regression.runs import compare_runs
from evaltrim.store import get_kv, put_kv


def _fingerprint(cases: list[dict[str, Any]]) -> str:
    raw = json.dumps(cases, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compare_experiments(
    baseline: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    label: str = "experiment",
) -> dict[str, Any]:
    key = "experiment:" + _fingerprint(baseline) + ":" + _fingerprint(current)
    cached = get_kv(key)
    if cached:
        cached["cache"] = "hit"
        return cached
    cmp = compare_runs(baseline, current)
    quality = {
        "pass_before": sum(1 for c in baseline if c.get("passed")),
        "pass_after": sum(1 for c in current if c.get("passed")),
        "n_before": len(baseline),
        "n_after": len(current),
    }
    latency = {
        "before": _mean([float(c.get("latency_ms") or 0) for c in baseline]),
        "after": _mean([float(c.get("latency_ms") or 0) for c in current]),
    }
    cost = {
        "before": _mean([float(c.get("cost_usd") or 0) for c in baseline]),
        "after": _mean([float(c.get("cost_usd") or 0) for c in current]),
    }
    by_b = {str(c.get("id")): c for c in baseline}
    by_c = {str(c.get("id")): c for c in current}
    tools = {
        "changed": sum(
            1
            for kid in sorted(set(by_b) & set(by_c))
            if (by_b[kid].get("tool_calls") or []) != (by_c[kid].get("tool_calls") or [])
        )
    }
    payload = {
        "label": label,
        "quality": quality,
        "latency_ms": latency,
        "cost_usd": cost,
        "tool_behavior": tools,
        "regression": cmp["counts"],
        "critical_failures": [c["id"] for c in cmp["cases"] if c.get("class") == "CONFIRMED_REGRESSION"],
        "cache": "miss",
        "note": "Comparison is deterministic for the same recorded cases. Not a live model call.",
    }
    put_kv("experiment", key, {**payload, "cache": "hit"})
    return payload


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
