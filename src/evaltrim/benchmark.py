"""Benchmark harness: precision/recall vs ground truth, safety, runtime, repeatability."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from evaltrim.analyze import analyze_suite
from evaltrim.models import RecommendationState, TestSuite
from evaltrim.parser import load_suite


def load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_benchmark(suite_path: Path, metadata_path: Path | None = None) -> dict[str, Any]:
    suite = load_suite(suite_path)
    meta = load_metadata(metadata_path or suite_path.parent / "benchmark_metadata.yaml")
    t0 = time.perf_counter()
    result = analyze_suite(suite)
    elapsed = time.perf_counter() - t0
    result2 = analyze_suite(suite)
    deterministic = _equivalent(result, result2)

    redundant_pred = _predicted_redundant_groups(result, suite)
    expected_groups = [set(g) for g in meta.get("expected_redundant_groups", [])]
    precision, recall = _set_prf(redundant_pred, expected_groups)
    f1 = None
    fpr = None
    if precision is not None and recall is not None:
        f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) else 0.0
        fpr = round(1.0 - precision, 4)
    expected_critical = set(meta.get("expected_critical_cases", []))
    retire_ids = {r.test_id for r in result.recommendations if r.state == RecommendationState.RETIRE}
    unsafe_retire = sorted(retire_ids & expected_critical)
    retirement_safety = 1.0 if not unsafe_retire else 0.0
    false_retirement_rate = round(len(unsafe_retire) / max(len(retire_ids), 1), 4) if retire_ids else 0.0

    expected_unique = set(meta.get("expected_unique_witnesses", []))
    pred_unique = {w.test_id for w in result.witnesses if w.is_unique_witness}
    unique_precision, unique_recall = _binary_prf(pred_unique, expected_unique)
    labeled_critical_witnesses = expected_unique & expected_critical
    pred_crit = {w.test_id for w in result.witnesses if w.is_critical_witness}
    false_critical_witnesses = sorted(pred_crit - expected_critical)
    crit_cov_recall = None
    if labeled_critical_witnesses:
        crit_cov_recall = round(len(labeled_critical_witnesses & pred_unique) / len(labeled_critical_witnesses), 4)
    false_witness_rate = None
    if pred_unique:
        false_witness_rate = round(len(pred_unique - expected_unique) / len(pred_unique), 4)
    elif expected_unique:
        false_witness_rate = 0.0
    crit_w_prec = None
    if pred_crit:
        crit_w_prec = round(len(pred_crit & expected_critical) / len(pred_crit), 4)
    elif labeled_critical_witnesses:
        crit_w_prec = 0.0
    else:
        crit_w_prec = 1.0

    reduction = result.summary.estimated_ci_reduction
    return {
        "suite": str(suite_path),
        "tests": result.summary.test_count,
        "runtime_seconds": round(elapsed, 4),
        "deterministic": deterministic,
        "redundancy_precision": precision,
        "redundancy_recall": recall,
        "redundancy_f1": f1,
        "false_positive_rate": fpr,
        "false_retirement_rate": false_retirement_rate,
        "unique_witness_precision": unique_precision,
        "unique_witness_recall": unique_recall,
        "false_witness_rate": false_witness_rate,
        "critical_witness_recall": crit_cov_recall,
        "critical_witness_precision": crit_w_prec,
        "false_critical_witnesses": false_critical_witnesses,
        "false_critical_witness_count": len(false_critical_witnesses),
        "retirement_safety_rate": retirement_safety,
        "unsafe_retirements": unsafe_retire,
        "critical_coverage": result.coverage.critical_coverage,
        "suite_reduction": reduction,
        "keep": result.summary.keep,
        "merge": result.summary.merge,
        "retire": result.summary.retire,
        "review": result.summary.review,
        "predicted_redundant_groups": [sorted(g) for g in redundant_pred],
        "unique_witness_predicted_ids": sorted(pred_unique),
        "unique_witness_expected_ids": sorted(expected_unique),
        "critical_witness_predicted_ids": sorted(pred_crit),
    }


def run_all_benchmarks(root: Path) -> dict[str, Any]:
    suites = sorted(root.glob("*/suite.yaml"))
    results = []
    for suite_path in suites:
        if suite_path.parent.name in {"competitive", "baseline"}:
            continue
        results.append(run_benchmark(suite_path, suite_path.parent / "benchmark_metadata.yaml"))
    return {
        "benchmarks": results,
        "targets": {
            "redundancy_precision": 0.90,
            "critical_coverage_preservation": 1.0,
            "suite_reduction": [0.20, 0.40],
            "runtime_seconds_per_1000": 60,
            "deterministic_repeatability": True,
            "note": "These are target metrics, not claims. Compare measured values below.",
        },
    }


def _predicted_redundant_groups(result, suite: TestSuite) -> list[set[str]]:
    parent: dict[str, str] = {t.id: t.id for t in suite.tests}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for pair in result.pairs:
        if pair.recommendation in {RecommendationState.MERGE, RecommendationState.RETIRE}:
            union(pair.left_id, pair.right_id)
    groups: dict[str, set[str]] = {}
    for tid in parent:
        groups.setdefault(find(tid), set()).add(tid)
    return [g for g in groups.values() if len(g) > 1]


def _set_prf(predicted: list[set[str]], expected: list[set[str]]) -> tuple[float | None, float | None]:
    if not expected:
        return None, None
    # A predicted group is a true positive if it equals or is a subset of an expected group
    # with at least 2 overlapping ids, using pair-level scoring for stability.
    exp_pairs = _pairs(expected)
    pred_pairs = _pairs(predicted)
    if not pred_pairs and not exp_pairs:
        return 1.0, 1.0
    if not pred_pairs:
        return 0.0, 0.0
    tp = len(pred_pairs & exp_pairs)
    precision = tp / len(pred_pairs) if pred_pairs else 0.0
    recall = tp / len(exp_pairs) if exp_pairs else 0.0
    return round(precision, 4), round(recall, 4)


def _pairs(groups: Iterable[set[str]]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for group in groups:
        items = sorted(group)
        for i, a in enumerate(items):
            for b in items[i + 1 :]:
                out.add((a, b))
    return out


def _binary_prf(pred: set[str], expected: set[str]) -> tuple[float | None, float | None]:
    if not expected:
        return None, None
    tp = len(pred & expected)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(expected) if expected else 0.0
    return round(precision, 4), round(recall, 4)


def _equivalent(a, b) -> bool:
    def dump(result):
        recs = [r.model_dump(mode="json") for r in result.recommendations]
        return json.dumps(recs, sort_keys=True)

    return dump(a) == dump(b)


def retirement_safety_check(suite: TestSuite, critical_ids: set[str]) -> bool:
    result = analyze_suite(suite)
    retire = {r.test_id for r in result.recommendations if r.state == RecommendationState.RETIRE}
    return retire.isdisjoint(critical_ids)


def generate_scale_suite(n: int, *, seed: int = 7) -> TestSuite:
    """Deterministic synthetic suite for runtime measurement. Not a quality benchmark."""
    from evaltrim.models import Tags, TestCase

    domains = ["refund", "privacy", "coding", "shopping"]
    actions = ["escalation", "refusal", "execution", "confirmation"]
    tests: list[TestCase] = []
    for i in range(n):
        domain = domains[i % len(domains)]
        action = actions[i % len(actions)]
        amount = 400 + (i % 5) * 50
        case = TestCase(
            id=f"gen-{i:05d}",
            input=f"{domain} request amount ${amount} case {i // 17}",
            expected=f"Agent should apply {action} for {domain}.",
            tags=Tags(domain=domain, action=action, behavior=[action], critical=i % 23 == 0),
        )
        if i % 17 == 1 and i > 0:
            prev = tests[i - 1]
            case = case.model_copy(update={"input": prev.input, "expected": prev.expected, "tags": prev.tags})
        tests.append(case)
    return TestSuite(
        name=f"scale-{n}",
        tests=tests,
        critical_behaviors=["payment", "privacy"],
        description="Generated runtime fixture",
    )


def run_scale_benchmark(sizes: list[int]) -> list[dict[str, Any]]:
    import tracemalloc

    rows = []
    for n in sizes:
        suite = generate_scale_suite(n)
        tracemalloc.start()
        t0 = time.perf_counter()
        result = analyze_suite(suite)
        elapsed = time.perf_counter() - t0
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        rows.append(
            {
                "tests": n,
                "runtime_seconds": round(elapsed, 4),
                "peak_mib": round(peak / (1024 * 1024), 2),
                "candidate_pairs": result.candidate_pairs_considered,
                "simulations_executed": result.timings.get("simulations_executed"),
                "simulation_cache_entries": result.timings.get("simulation_cache_entries"),
                "timings": result.timings,
                "keep": result.summary.keep,
                "merge": result.summary.merge,
                "retire": result.summary.retire,
                "review": result.summary.review,
            }
        )
    return rows


def run_incremental_scale_benchmark(*, n: int = 10000, changed: int = 5) -> dict[str, Any]:
    """Warm-cache a large suite, mutate `changed` tests, re-analyze with pair cache on."""
    import os

    suite = generate_scale_suite(n)
    prev = os.environ.get("EVALTRIM_NO_CACHE")
    if prev is not None:
        os.environ.pop("EVALTRIM_NO_CACHE", None)
    t_cold = None
    try:
        t0 = time.perf_counter()
        analyze_suite(suite, use_cache=True)
        t_cold = time.perf_counter() - t0
        mutated = []
        for i, test in enumerate(suite.tests):
            if i < changed:
                mutated.append(
                    test.model_copy(
                        update={"input": test.input + " [changed]", "expected": test.expected + " [changed]"}
                    )
                )
            else:
                mutated.append(test)
        suite2 = suite.model_copy(update={"tests": mutated})
        t1 = time.perf_counter()
        result = analyze_suite(suite2, use_cache=True)
        t_inc = time.perf_counter() - t1
    finally:
        if prev is not None:
            os.environ["EVALTRIM_NO_CACHE"] = prev
    return {
        "tests": n,
        "changed": changed,
        "cold_runtime_seconds": round(t_cold or 0.0, 4),
        "incremental_runtime_seconds": round(t_inc, 4),
        "pair_cache_hits": result.timings.get("pair_cache_hits"),
        "pair_cache_misses": result.timings.get("pair_cache_misses"),
        "note": "Unchanged pairs reuse persisted scores; coverage/removal still run on the full suite.",
    }
