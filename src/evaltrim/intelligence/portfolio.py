"""Select an evaluation subset under time/cost/count budgets.

Greedy heuristic. Not a globally optimal solver. Alternatives are near-ties.
"""

from __future__ import annotations

from typing import Any

from evaltrim.models import AnalysisResult, TestSuite


def select_portfolio(
    suite: TestSuite,
    result: AnalysisResult,
    *,
    max_tests: int | None = None,
    max_cost: float | None = None,
    max_time_ms: float | None = None,
) -> dict[str, Any]:
    by_id = {t.id: t for t in suite.tests}
    ev_by = {e.test_id: e for e in result.evidence}
    wit_by = {w.test_id: w for w in result.witnesses}

    def cost(tid: str) -> float:
        stats = by_id[tid].run_stats
        return float(stats.estimated_cost_usd) if stats and stats.estimated_cost_usd else 1.0

    def latency(tid: str) -> float:
        stats = by_id[tid].run_stats
        return float(stats.average_latency_ms) if stats and stats.average_latency_ms else 1.0

    def score(tid: str) -> float:
        ev = ev_by[tid]
        w = wit_by[tid]
        s = 0.0
        if ev.is_critical_witness or w.unique_critical:
            s += 100.0
        if w.unique_atoms:
            s += 40.0
        if w.unique_boundary:
            s += 30.0
        if w.unique_requirement:
            s += 35.0
        if w.unique_failure or w.unique_failure_family:
            s += 20.0
        s += ev.value_score / 5.0
        if ev.stale:
            s -= 5.0
        return s

    ranked = sorted(by_id, key=lambda tid: (-score(tid), tid))
    selected: list[str] = []
    used_cost = 0.0
    used_time = 0.0
    for tid in ranked:
        if max_tests is not None and len(selected) >= max_tests:
            break
        next_cost = used_cost + cost(tid)
        next_time = used_time + latency(tid)
        if max_cost is not None and next_cost > max_cost and selected:
            continue
        if max_time_ms is not None and next_time > max_time_ms and selected:
            continue
        # Always admit unique critical witnesses even if they exceed a soft budget.
        if wit_by[tid].unique_critical or ev_by[tid].is_critical_witness:
            selected.append(tid)
            used_cost = next_cost
            used_time = next_time
            continue
        if max_cost is not None and next_cost > max_cost:
            continue
        if max_time_ms is not None and next_time > max_time_ms:
            continue
        selected.append(tid)
        used_cost = next_cost
        used_time = next_time

    leftover = [tid for tid in ranked if tid not in selected]
    # Lightweight 1-opt: swap the lowest-scoring optional test with a leftover if it scores higher.
    optional = [tid for tid in selected if not (wit_by[tid].unique_critical or ev_by[tid].is_critical_witness)]
    if leftover and optional:
        weakest = min(optional, key=lambda tid: (score(tid), tid))
        best = leftover[0]
        if score(best) > score(weakest):
            alt_cost = used_cost - cost(weakest) + cost(best)
            alt_time = used_time - latency(weakest) + latency(best)
            ok_cost = max_cost is None or alt_cost <= max_cost
            ok_time = max_time_ms is None or alt_time <= max_time_ms
            if ok_cost and ok_time:
                selected = [tid if tid != weakest else best for tid in selected]
                used_cost, used_time = alt_cost, alt_time
    alt = list(selected)
    if leftover:
        extras = [tid for tid in leftover if tid not in selected]
        if extras and len(alt) >= 2:
            alt = alt[:-1] + extras[:1]
    return {
        "selected": selected,
        "alternatives": [alt] if alt != selected else [],
        "used_cost": round(used_cost, 4),
        "used_time_ms": round(used_time, 4),
        "constraints": {"max_tests": max_tests, "max_cost": max_cost, "max_time_ms": max_time_ms},
        "evidence": {
            tid: {
                "score": score(tid),
                "critical_witness": bool(wit_by[tid].unique_critical or ev_by[tid].is_critical_witness),
                "unique_atoms": list(wit_by[tid].unique_atoms),
            }
            for tid in selected
        },
        "note": (
            "Portfolio starts greedy (critical witnesses first) then applies a single optional swap. "
            "Not a globally optimal solver."
        ),
    }
