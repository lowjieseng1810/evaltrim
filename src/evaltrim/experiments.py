"""Deterministic experiment / model / prompt / tool comparison with result reuse."""

from __future__ import annotations

import hashlib
import json
from itertools import product
from typing import Any

from evaltrim.evaluation.statistics import compare_samples
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
    stats = compare_samples(
        [float(c.get("latency_ms") or 0) for c in baseline],
        [float(c.get("latency_ms") or 0) for c in current],
    )
    payload = {
        "label": label,
        "quality": quality,
        "latency_ms": latency,
        "cost_usd": cost,
        "tool_behavior": tools,
        "regression": cmp["counts"],
        "critical_failures": [c["id"] for c in cmp["cases"] if c.get("class") == "CONFIRMED_REGRESSION"],
        "latency_significance": stats,
        "cache": "miss",
        "note": "Comparison is deterministic for the same recorded cases. Not a live model call.",
    }
    put_kv("experiment", key, {**payload, "cache": "hit"})
    return payload


def experiment_matrix(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Each run: {id, dimensions{model,prompt,tools,dataset}, cases: [...]}."""
    scored = []
    for run in runs:
        cases = run.get("cases") or []
        quality = sum(1 for c in cases if c.get("passed")) / max(len(cases), 1)
        cost = _mean([float(c.get("cost_usd") or 0) for c in cases])
        latency = _mean([float(c.get("latency_ms") or 0) for c in cases])
        scored.append(
            {
                "id": run.get("id"),
                "dimensions": run.get("dimensions") or {},
                "quality": round(quality, 6),
                "cost": cost,
                "latency": latency,
                "n": len(cases),
            }
        )
    if not scored:
        return {"runs": [], "note": "empty matrix"}

    def _qcl(row: dict[str, Any]) -> tuple[float, float, float, str]:
        return (float(row["quality"]), float(row["cost"]), float(row["latency"]), str(row["id"]))

    best_quality = max(scored, key=lambda r: (_qcl(r)[0], -_qcl(r)[1], -_qcl(r)[2], _qcl(r)[3]))
    best_cost = min(scored, key=lambda r: (_qcl(r)[1], -_qcl(r)[0], _qcl(r)[2], _qcl(r)[3]))
    best_latency = min(scored, key=lambda r: (_qcl(r)[2], -_qcl(r)[0], _qcl(r)[1], _qcl(r)[3]))
    pareto = _pareto(scored)
    best_pareto = max(
        pareto,
        key=lambda r: (float(r["quality"]), -float(r["cost"]), -float(r["latency"]), str(r["id"])),
    )
    return {
        "runs": scored,
        "BEST_QUALITY": best_quality,
        "BEST_COST": best_cost,
        "BEST_LATENCY": best_latency,
        "BEST_PARETO_OPTION": best_pareto,
        "pareto_frontier": pareto,
        "note": "Pareto over maximize quality, minimize cost, minimize latency. Evidence is recorded metrics only.",
    }


def expand_dimensions(axes: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = sorted(axes)
    combos = []
    for values in product(*(axes[k] for k in keys)):
        combos.append(dict(zip(keys, values, strict=True)))
    return combos


def _pareto(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontier = []
    for a in rows:
        dominated = False
        for b in rows:
            if b["id"] == a["id"]:
                continue
            if (
                b["quality"] >= a["quality"]
                and b["cost"] <= a["cost"]
                and b["latency"] <= a["latency"]
                and (b["quality"] > a["quality"] or b["cost"] < a["cost"] or b["latency"] < a["latency"])
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(a)
    frontier.sort(key=lambda r: (-float(r["quality"]), float(r["cost"]), float(r["latency"]), str(r["id"])))
    return frontier


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
