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
        if w.unique_critical:
            s += 100.0
        if getattr(w, "is_unique_witness", False):
            s += 50.0
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
            "Not a globally optimal solver. Do not treat selected sets as mathematically optimal."
        ),
    }


def named_portfolios(
    suite: TestSuite,
    result: AnalysisResult,
    *,
    max_tests: int | None = None,
    max_cost: float | None = None,
    max_time_ms: float | None = None,
) -> dict[str, Any]:
    n = len(suite.tests)
    compact_n = max(1, n // 3) if max_tests is None else min(max_tests, n)
    compact = select_portfolio(suite, result, max_tests=compact_n, max_cost=max_cost, max_time_ms=max_time_ms)
    critical_ids = [e.test_id for e in result.evidence if e.is_critical_witness or (e.behavior.critical)]
    critical = select_portfolio(
        suite, result, max_tests=max(len(critical_ids), 1), max_cost=max_cost, max_time_ms=max_time_ms
    )
    # Prefer members that are critical witnesses if the greedy set drifted.
    keep_n = max(len(critical_ids), 1)
    critical["selected"] = sorted(set(critical["selected"]) | set(critical_ids))[:keep_n]
    total_cost = 0.0
    for t in suite.tests:
        stats = t.run_stats
        total_cost += float(stats.estimated_cost_usd) if stats and stats.estimated_cost_usd else 1.0
    cost_budget = max_cost if max_cost is not None else max(total_cost / 2.0, 1e-9)
    cost = select_portfolio(suite, result, max_tests=max_tests or n, max_cost=cost_budget, max_time_ms=max_time_ms)
    witness = witness_portfolio(suite, result)
    return {
        "BEST_COMPACT_PORTFOLIO": compact,
        "BEST_CRITICAL_PORTFOLIO": critical,
        "BEST_COST_CONSTRAINED_PORTFOLIO": cost,
        "BEST_WITNESS_PORTFOLIO": witness,
        "pareto": pareto_portfolios(suite, result, max_tests=max_tests),
        "note": "Named portfolios are greedy heuristics with Pareto alternatives, not proven optima.",
    }


def witness_portfolio(suite: TestSuite, result: AnalysisResult) -> dict[str, Any]:
    """Compact subset that keeps every coverage/critical witness. Not a minimum hitting set solver."""
    must = [
        w.test_id
        for w in result.witnesses
        if w.is_unique_witness or w.is_critical_witness or w.unique_requirement or w.unique_boundary
    ]
    must = sorted(set(must))
    optional = [t.id for t in suite.tests if t.id not in must]
    alt = list(must)
    if optional:
        alt = must + optional[:1]
    return {
        "selected": must,
        "alternatives": [alt] if alt != must else [],
        "minimum_practical_witness_set": must,
        "near_minimal_alternatives": [alt] if alt != must else [],
        "suite_size": len(suite.tests),
        "witness_set_size": len(must),
        "coverage_retained": 1.0 if must else 0.0,
        "critical_coverage": 1.0 if must else 0.0,
        "critical_ids": [w.test_id for w in result.witnesses if w.is_critical_witness],
        "runtime_note": "Subset selection is O(n) over classified witnesses; suite analysis time is separate.",
        "note": (
            "MINIMUM PRACTICAL WITNESS SET keeps tests classified as coverage witnesses. "
            "Not a mathematically optimal hitting set."
        ),
    }


def pareto_portfolios(
    suite: TestSuite, result: AnalysisResult, *, max_tests: int | None = None
) -> list[dict[str, Any]]:
    """A few budget points, not a full multi-objective solver."""
    n = len(suite.tests)
    sizes = sorted({max(1, n // 4), max(1, n // 2), n if max_tests is None else min(n, max_tests)})
    if max_tests:
        sizes = sorted(set(sizes) | {max_tests})
    out = []
    for size in sizes:
        row = select_portfolio(suite, result, max_tests=size)
        out.append(
            {
                "max_tests": size,
                "selected": row["selected"],
                "used_cost": row["used_cost"],
                "used_time_ms": row["used_time_ms"],
            }
        )
    return out
