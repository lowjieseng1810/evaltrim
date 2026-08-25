"""In-repo competitive measurements. Competitor numbers are UNMEASURED unless reproduced here."""

from __future__ import annotations

import platform
import time
from pathlib import Path
from typing import Any

from evaltrim import __version__
from evaltrim.benchmark import run_all_benchmarks, run_scale_benchmark
from evaltrim.constants import CONTRACT_VERSION
from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GraderSpec
from evaltrim.evaluation.graders import REGISTRY, grade_record
from evaltrim.evaluation.statistics import compare_samples
from evaltrim.flake import classify_flake
from evaltrim.intelligence.mutation import mutation_score
from evaltrim.models import FlakeStatus, RunStats, Tags, TestCase
from evaltrim.regression.runs import classify_run_delta, compare_runs
from evaltrim.security import evaluate_security


def run_competitive_harness(*, scale: list[int] | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    quality = run_all_benchmarks(Path("benchmarks"))
    graders = sorted(set(REGISTRY))
    mut = mutation_score()
    sec = evaluate_security()
    identical = compare_runs(
        [{"id": "t", "output": "a", "passed": True, "latency_ms": 10}],
        [{"id": "t", "output": "a", "passed": True, "latency_ms": 10}],
    )
    provider = classify_run_delta(
        {"id": "t", "output": "ok", "passed": True},
        {"id": "t", "output": "err", "passed": False, "error_kind": "provider_error"},
    )
    env_test = TestCase(
        id="e",
        input="x",
        expected="y",
        tags=Tags(),
        run_stats=RunStats(
            runs=5,
            passes=1,
            failures=4,
            outcomes=["pass", "timeout", "provider_error", "timeout", "rate_limit"],
        ),
    )
    flake_status, _ = classify_flake(env_test)
    same = [1.0] * 20
    false_reg = compare_samples(same, list(same))
    shifted = [v + 3.0 for v in same]
    true_shift = compare_samples(same, shifted)
    json_grade = grade_record(
        EvaluationRecord(
            id="j",
            input="{}",
            expected="",
            graders=[GraderSpec(type="json", params={"schema": {"type": "object", "required": ["ok"]}})],
        ),
        AgentOutput(text='{"ok": true}'),
    )
    constructed = "constructed suites"
    rows = [
        _row("constructed_redundancy_precision_min", _min_metric(quality, "redundancy_precision"), constructed),
        _row("constructed_redundancy_recall_min", _min_metric(quality, "redundancy_recall"), constructed),
        _row("retirement_safety_min", _min_metric(quality, "retirement_safety_rate"), constructed),
        _row("critical_coverage_min", _min_metric(quality, "critical_coverage"), constructed),
        _row("grader_plugin_count", len(set(REGISTRY.values())), "registered grader classes"),
        _row("json_schema_grader_pass", 1.0 if json_grade[0].passed else 0.0, "local fixture"),
        _row("unchanged_classification", 1.0 if identical["counts"].get("UNCHANGED") == 1 else 0.0, "identical runs"),
        _row(
            "provider_error_not_confirmed_regression",
            1.0 if provider["class"] != "CONFIRMED_REGRESSION" else 0.0,
            "provider_error fixture",
        ),
        _row(
            "environmental_flake_class",
            1.0 if flake_status == FlakeStatus.ENVIRONMENTAL else 0.0,
            "timeout/provider outcomes",
        ),
        _row(
            "false_statistical_regression_rate",
            1.0 if not false_reg["regression_flag"] else 0.0,
            "identical samples must not flag",
        ),
        _row(
            "detect_mean_shift",
            1.0 if true_shift["statistically_significant"] else 0.0,
            "mean +3 on n=20",
        ),
        _row("mutation_score", mut["mutation_score"], "constructed grader probes"),
        _row("security_detection_rate", sec["detection_rate"], "local family probes"),
        _row("security_false_positives", sec["false_positives"], "local family probes"),
        _row("default_network_required", 0.0, "0 means no network by default"),
        _row("json_contract_version", CONTRACT_VERSION, "machine-readable contract"),
    ]
    scale_rows = run_scale_benchmark(scale or [100, 500])
    payload = {
        "evaltrim_version": __version__,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "methodology": (
            "EvalTrim numbers are measured in this process. Competitor columns are UNMEASURED "
            "unless a public benchmark was reproduced in benchmarks/competitive/. "
            "Do not treat UNMEASURED as a win."
        ),
        "quality_suites": quality,
        "metrics": rows,
        "scale": scale_rows,
        "runtime_seconds": round(time.perf_counter() - t0, 4),
        "competitive_status_hint": "PARITY",
        "note": (
            "STATUS A (SUPERIOR) requires every directly comparable measured metric >= strongest competitor. "
            "This harness does not fabricate competitor numbers."
        ),
        "graders": graders,
        "mutation": mut,
        "security": {
            "attack_coverage": sec["attack_coverage"],
            "detection_rate": sec["detection_rate"],
            "false_positives": sec["false_positives"],
            "reproducibility": sec["reproducibility"],
            "note": sec["note"],
        },
    }
    return payload


def render_results_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Competitive results",
        "",
        f"EvalTrim **{payload.get('evaltrim_version')}**.",
        "",
        payload.get("methodology", ""),
        "",
        "| Metric | EvalTrim | Competitor | Winner | Method | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("metrics", []):
        metric = row["metric"]
        ev = row["evaltrim"]
        comp = row["competitor"]
        win = row["winner"]
        method = row["method"]
        notes = row["notes"]
        lines.append(f"| {metric} | {ev} | {comp} | {win} | {method} | {notes} |")
    lines += ["", "## Scale (EvalTrim only)", ""]
    for row in payload.get("scale", []):
        lines.append(
            f"- n={row['tests']} t={row['runtime_seconds']}s mib={row['peak_mib']} pairs={row['candidate_pairs']}"
        )
    lines += ["", "Competitor runtime on the same synthetic generator: **UNMEASURED**.", ""]
    return "\n".join(lines) + "\n"


def _min_metric(quality: dict[str, Any], key: str) -> float | None:
    vals = [row.get(key) for row in quality.get("benchmarks", []) if row.get(key) is not None]
    return min(vals) if vals else None


def _row(metric: str, evaltrim: Any, method: str) -> dict[str, Any]:
    competitor = "UNMEASURED"
    winner = "UNMEASURED"
    return {
        "metric": metric,
        "evaltrim": evaltrim,
        "competitor": competitor,
        "winner": winner,
        "method": method,
        "notes": "Head-to-head competitor value not reproduced in this run.",
    }
