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
        "verdict": _experiment_verdict(quality, cost, latency, stats),
        "cache": "miss",
        "note": "Comparison is deterministic for the same recorded cases. Not a live model call.",
        "reproducible": True,
        "manifest_fingerprint": key,
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
        "BEST_PARETO": best_pareto,
        "BEST_PARETO_OPTION": best_pareto,
        "pareto_frontier": pareto,
        "note": (
            "Pareto over maximize quality, minimize cost, minimize latency. "
            "Evidence is recorded metrics only. Not a proven global optimum."
        ),
    }


def expand_dimensions(axes: dict[str, list[Any]]) -> list[dict[str, Any]]:
    keys = sorted(axes)
    combos = []
    for values in product(*(axes[k] for k in keys)):
        combos.append(dict(zip(keys, values, strict=True)))
    return combos


def plan_experiment(
    axes: dict[str, list[Any]],
    *,
    dry_run: bool = False,
    smoke: bool = False,
    repeats: int = 1,
) -> dict[str, Any]:
    combos = expand_dimensions(axes)
    if smoke:
        combos = combos[:1]
    return {
        "combos": combos,
        "n": len(combos),
        "repeats": repeats,
        "dry_run": dry_run,
        "smoke": smoke,
        "note": "Dry/smoke planning only. Execute recorded runs separately; no live provider calls.",
    }


def write_manifest(path: Any, payload: dict[str, Any]) -> None:
    from pathlib import Path

    dest = Path(path)
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_manifest(path: Any) -> dict[str, Any]:
    from pathlib import Path

    return json.loads(Path(path).read_text(encoding="utf-8"))


def replay_manifest(path: Any) -> dict[str, Any]:
    """Recompute matrix/compare from a saved manifest. Same bytes → same verdicts."""
    data = load_manifest(path)
    if "runs" in data:
        return experiment_matrix(data["runs"])
    if "baseline" in data and "current" in data:
        return compare_experiments(data["baseline"], data["current"], label=str(data.get("label") or "experiment"))
    raise ValueError("manifest must contain runs or baseline/current cases")


def _experiment_verdict(
    quality: dict[str, Any],
    cost: dict[str, float],
    latency: dict[str, float],
    stats: dict[str, Any],
) -> dict[str, Any]:
    n = max(int(quality.get("n_after") or 0), 1)
    q_before = (quality.get("pass_before") or 0) / max(int(quality.get("n_before") or 0), 1)
    q_after = (quality.get("pass_after") or 0) / n
    dq = q_after - q_before
    dc = float(cost["after"]) - float(cost["before"])
    tiny = abs(dq) < 0.02 and abs(dc) < 0.01
    significant = bool(stats.get("statistically_significant"))
    practical = bool(stats.get("practically_significant", not tiny))
    if dq > 0.02 and dc <= 0:
        label = "RECOMMENDED"
        why = "Quality improved without a cost increase."
    elif dq > 0.02 and dc > 0:
        label = "TRADEOFF"
        why = "Quality improved with a cost regression."
    elif dq < -0.02:
        label = "REGRESSION"
        why = "Quality dropped. Lower cost does not excuse a quality regression."
    elif significant and tiny:
        label = "INCONCLUSIVE"
        why = "Statistically significant but practically tiny change."
    elif not significant and tiny:
        label = "INCONCLUSIVE"
        why = "No meaningful quality or cost movement."
    else:
        label = "TRADEOFF" if dq >= 0 else "REGRESSION"
        why = "Mixed quality/cost/latency movement; inspect evidence."
    return {
        "label": label,
        "why": why,
        "quality_delta": round(dq, 4),
        "cost_delta": round(dc, 4),
        "latency_delta": round(float(latency["after"]) - float(latency["before"]), 4),
        "statistically_significant": significant,
        "practically_tiny": tiny and not practical,
        "evidence": {"quality": quality, "cost": cost, "latency": latency},
        "risk": "HIGH" if label == "REGRESSION" else ("MEDIUM" if label == "TRADEOFF" else "LOW"),
        "recommended_action": label,
    }


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
