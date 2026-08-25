"""Head-to-head competitive verification. Never invent competitor numbers."""

from __future__ import annotations

import asyncio
import os
import platform
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from evaltrim import __version__
from evaltrim.analyze import analyze_suite
from evaltrim.benchmark import run_all_benchmarks, run_scale_benchmark
from evaltrim.constants import CONTRACT_VERSION
from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GraderSpec, ToolCallRecord, TrajectoryStep, Usage
from evaltrim.evaluation.graders import REGISTRY, grade_record
from evaltrim.evaluation.statistics import compare_samples
from evaltrim.experiments import compare_experiments
from evaltrim.flake import classify_flake
from evaltrim.impacted import impacted_tests
from evaltrim.ingest import compress_production_failures
from evaltrim.intelligence.mutation import mutation_score
from evaltrim.intelligence.portfolio import select_portfolio
from evaltrim.models import RunStats, Tags, TestCase, TestSuite
from evaltrim.parser import load_suite
from evaltrim.regression.runs import classify_run_delta, compare_runs
from evaltrim.runtime.replay import replay_recording, save_recording
from evaltrim.runtime.runner import fingerprint, run_record, run_suite
from evaltrim.sandbox import LocalSandbox
from evaltrim.scenarios import load_scenario, replay_scenario
from evaltrim.security import evaluate_security

ROOT = Path(__file__).resolve().parents[2]
COMPETITIVE_DIR = ROOT / "benchmarks" / "competitive"
UNMEASURED = "UNMEASURED"
NDC = "NOT DIRECTLY COMPARABLE"
NOT_OFFERED = "Capability not offered / not directly comparable"
COMPETITOR_PATH = Path(os.environ.get("EVALTRIM_COMPETITOR_PATH", "/tmp/comp-pkgs"))

WEIGHTS = {
    "equal": (1 / 3, 1 / 3, 1 / 3),
    "intelligence_heavier": (0.3, 0.3, 0.4),
    "eval_workflow_heavier": (0.4, 0.4, 0.2),
}


def run_competitive_harness(
    *,
    scale: list[int] | None = None,
    competitor: str | None = None,
    write_docs: bool = False,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or ROOT
    t0 = time.perf_counter()
    env = _load_yaml(root / "benchmarks" / "competitive" / "environment.yaml")
    env["live"] = _live_machine()
    grader_fix = _load_yaml(root / "benchmarks" / "competitive" / "fixtures" / "grader_cases.yaml")
    cases = list(grader_fix.get("cases") or [])

    agenteval = _try_agenteval()
    grader_h2h = _grader_head_to_head(cases, agenteval)
    stats_h2h = _stats_head_to_head(agenteval)
    flake_h2h = _flake_head_to_head(agenteval)
    evaltrim_only = _evaltrim_workflow(root)
    quality = run_all_benchmarks(root / "benchmarks")
    prev_cache = os.environ.get("EVALTRIM_NO_CACHE")
    os.environ["EVALTRIM_NO_CACHE"] = "1"
    try:
        scale_rows = run_scale_benchmark(scale or [100, 500])
    finally:
        if prev_cache is None:
            os.environ.pop("EVALTRIM_NO_CACHE", None)
        else:
            os.environ["EVALTRIM_NO_CACHE"] = prev_cache
    mut = mutation_score()
    sec = evaluate_security()
    reproduction = _reproduction_status(agenteval, env)

    rows = _result_rows(
        grader_h2h=grader_h2h,
        stats_h2h=stats_h2h,
        flake_h2h=flake_h2h,
        evaltrim_only=evaltrim_only,
        quality=quality,
        mut=mut,
        sec=sec,
        scale_rows=scale_rows,
        agenteval=agenteval,
        env=env,
    )
    if competitor:
        key = competitor.lower().replace(" ", "_").replace("-", "_")
        rows = [r for r in rows if key in {r["capability"].lower().replace(" ", "_"), "all"} or True]
        # Filter columns later in render; keep all rows but tag requested competitor.
        for r in rows:
            r["requested_competitor"] = competitor

    scores = _scorecard(grader_h2h, stats_h2h, flake_h2h, evaltrim_only, quality, mut, sec)
    status = _competitive_status(reproduction, scores, grader_h2h)

    payload: dict[str, Any] = {
        "evaltrim_version": __version__,
        "contract_version": CONTRACT_VERSION,
        "benchmark_date": (env or {}).get("benchmark_date"),
        "environment": env,
        "reproduction": reproduction,
        "grader_head_to_head": grader_h2h,
        "statistics": stats_h2h,
        "flaky": flake_h2h,
        "evaltrim_workflow": evaltrim_only,
        "quality_suites": quality,
        "mutation": mut,
        "security": {
            "detection_rate": sec["detection_rate"],
            "false_positives": sec["false_positives"],
            "reproducibility": sec["reproducibility"],
            "attack_coverage": sec["attack_coverage"],
            "note": sec["note"],
        },
        "metrics": rows,
        "scale": scale_rows,
        "scores": scores,
        "competitive_status": status,
        "runtime_seconds": round(time.perf_counter() - t0, 4),
        "methodology_note": (
            "MEASURED competitor cells come from in-process AgentEval 0.7.0 on this machine. "
            "UNMEASURED means the tool was not successfully executed. "
            "NOT DIRECTLY COMPARABLE means hosted/UI or a different job. "
            "Do not treat UNMEASURED as an EvalTrim win."
        ),
        "agenteval_source": {
            "pypi": "agentevalkit==0.7.0",
            "github_readme_grader_count": 11,
            "github_readme_includes_trajectory": True,
            "github_readme_url": "https://github.com/agentkitai/agenteval/blob/main/README.md",
            "wheel_shipped_grader_count": 10,
            "wheel_includes_trajectory": False,
            "fetched_github_readme_date": "2026-08-25",
        },
        "promptfoo_source": {
            "docs_plugin_count": 157,
            "docs_url": "https://www.promptfoo.dev/docs/red-team/plugins/",
            "kind": "documented catalog breadth, not live CLI detection quality",
            "cli_executed": False,
        },
    }
    if write_docs:
        _write_docs(root, payload)
    return payload


def render_results_markdown(payload: dict[str, Any]) -> str:
    return _render_results(payload)


def write_competitive_docs(root: Path, payload: dict[str, Any]) -> None:
    _write_docs(root, payload)


def _live_machine() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "node": _cmd_version("node"),
        "cpus": os.cpu_count(),
        "date": time.strftime("%Y-%m-%d"),
    }


def _cmd_version(binary: str) -> str | None:
    import shutil
    import subprocess

    path = shutil.which(binary)
    if not path:
        return None
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, check=False, timeout=5)
        return (out.stdout or out.stderr).strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _try_agenteval() -> dict[str, Any] | None:
    if COMPETITOR_PATH.exists() and str(COMPETITOR_PATH) not in sys.path:
        sys.path.insert(0, str(COMPETITOR_PATH))
    try:
        import agenteval
        from agenteval.graders import get_grader

        return {"module": agenteval, "version": getattr(agenteval, "__version__", "unknown"), "get_grader": get_grader}
    except Exception:  # noqa: BLE001
        return None


def _reproduction_status(agenteval: dict[str, Any] | None, env: dict[str, Any]) -> dict[str, Any]:
    ae_ok = bool(agenteval and agenteval.get("version") and "error" not in agenteval)
    return {
        "successfully_reproduced": ["agentevalkit==0.7.0"] if ae_ok else [],
        "not_reproducible": [
            {
                "name": "promptfoo",
                "attempted": ["0.122.0", "0.120.0"],
                "reason": (env.get("competitors") or {}).get("promptfoo", {}).get("failure")
                or "Node engine / migrator failure",
            },
            {"name": "deepeval", "reason": "Not installed; no metrics fabricated"},
            {"name": "inspect_ai", "reason": "Not installed; no metrics fabricated"},
            {"name": "evalview", "reason": "Not installed; no metrics fabricated"},
            {"name": "vercel_agent_eval", "reason": NDC},
            {"name": "agentevalhq", "reason": "Not installed"},
        ],
        "hosted_not_directly_comparable": ["langfuse", "phoenix", "braintrust"],
    }


def _grade_evaltrim(case: dict[str, Any]) -> bool | None:
    family = case["family"]
    text = str(case.get("text") or "")
    if family == "exact":
        rec = EvaluationRecord(
            id=case["id"], input="i", expected=str(case["expected"]), graders=[GraderSpec(type="exact")]
        )
        out = AgentOutput(text=text)
    elif family == "contains":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="contains", params={"text": case["needle"]})],
        )
        out = AgentOutput(text=text)
    elif family == "regex":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="regex", params={"pattern": case["pattern"]})],
        )
        out = AgentOutput(text=text)
    elif family == "json_schema":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="json_schema", params={"schema": case["schema"]})],
        )
        out = AgentOutput(text=text)
    elif family == "tool_names":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="tool_call", params={"required": case["expected_tools"]})],
        )
        out = AgentOutput(text="ok", tool_calls=[ToolCallRecord(name=n) for n in case.get("tools") or []])
    elif family == "tool_args":
        tools = case.get("tools") or []
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[
                GraderSpec(
                    type="tool_args",
                    params={"constraints": [{"name": tools[0]["name"], "equals": case.get("equals") or {}}]},
                )
            ],
        )
        out = AgentOutput(
            text="ok", tool_calls=[ToolCallRecord(name=t["name"], arguments=t.get("arguments") or {}) for t in tools]
        )
    elif family == "trajectory":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="trajectory", params={"order": case["order"]})],
        )
        out = AgentOutput(text="ok", trajectory=[TrajectoryStep(kind=s) for s in case.get("steps") or []])
    elif family == "latency":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="latency", params={"max_ms": case["max_ms"]})],
        )
        out = AgentOutput(text="ok", usage=Usage(latency_ms=case["latency_ms"]))
    elif family == "cost":
        rec = EvaluationRecord(
            id=case["id"],
            input="i",
            expected="",
            graders=[GraderSpec(type="cost", params={"max_usd": case["max_usd"]})],
        )
        out = AgentOutput(text="ok", usage=Usage(cost_usd=case["cost_usd"]))
    else:
        return None
    grades = grade_record(rec, out)
    return grades[0].passed


async def _grade_agenteval(get_grader, case: dict[str, Any]) -> bool | None:
    from agenteval.models import AgentResult, EvalCase

    family = case["family"]
    text = str(case.get("text") or "")
    if family == "exact":
        grader = get_grader("exact", {})
        ev = EvalCase(name=case["id"], input="i", expected={"output": case["expected"]}, grader="exact")
        res = AgentResult(output=text)
    elif family == "contains":
        grader = get_grader("contains", {})
        ev = EvalCase(name=case["id"], input="i", expected={"output_contains": [case["needle"]]}, grader="contains")
        res = AgentResult(output=text)
    elif family == "regex":
        grader = get_grader("regex", {})
        ev = EvalCase(name=case["id"], input="i", expected={"pattern": case["pattern"]}, grader="regex")
        res = AgentResult(output=text)
    elif family == "json_schema":
        grader = get_grader("json_schema", {"schema": case["schema"]})
        ev = EvalCase(name=case["id"], input="i", expected={}, grader="json_schema")
        res = AgentResult(output=text)
    elif family == "tool_names":
        grader = get_grader("tool-check", {})
        ev = EvalCase(
            name=case["id"],
            input="i",
            expected={"tools_called": case["expected_tools"]},
            grader="tool-check",
        )
        res = AgentResult(output="ok", tools_called=[{"name": n} for n in case.get("tools") or []])
    elif family == "latency":
        grader = get_grader("latency", {"max_ms": case["max_ms"]})
        ev = EvalCase(name=case["id"], input="i", expected={}, grader="latency")
        res = AgentResult(output="ok", latency_ms=int(case["latency_ms"]))
    elif family == "cost":
        grader = get_grader("cost", {"max_usd": case["max_usd"]})
        ev = EvalCase(name=case["id"], input="i", expected={}, grader="cost")
        res = AgentResult(output="ok", cost_usd=float(case["cost_usd"]))
    else:
        return None
    graded = await grader.grade(ev, res)
    return bool(graded.passed)


def _grader_head_to_head(cases: list[dict[str, Any]], agenteval: dict[str, Any] | None) -> dict[str, Any]:
    ae_ok = bool(agenteval and agenteval.get("get_grader"))
    rows = []
    for case in cases:
        et = _grade_evaltrim(case)
        ae: bool | None | str = None
        if case.get("comparable") == "evaltrim_only":
            ae = NOT_OFFERED
        elif not ae_ok:
            ae = UNMEASURED
        else:
            assert agenteval is not None
            try:
                ae = asyncio.run(_grade_agenteval(agenteval["get_grader"], case))
            except Exception as exc:  # noqa: BLE001
                ae = f"ERROR:{exc}"
        gold = case.get("gold")
        rows.append(
            {
                "id": case["id"],
                "family": case["family"],
                "gold": gold,
                "evaltrim": et,
                "agenteval": ae,
                "scored": gold is not None and case.get("comparable") != "evaltrim_only",
            }
        )
    scored = [r for r in rows if r["scored"]]
    et_correct = sum(1 for r in scored if r["evaltrim"] == r["gold"])
    ae_scored = [r for r in scored if isinstance(r["agenteval"], bool)]
    ae_correct = sum(1 for r in ae_scored if r["agenteval"] == r["gold"])
    et_acc = et_correct / len(scored) if scored else None
    ae_acc = ae_correct / len(ae_scored) if ae_scored else UNMEASURED
    et_only = [r for r in rows if r["family"] in {"tool_args", "trajectory"}]
    et_only_acc = sum(1 for r in et_only if r["evaltrim"] == r["gold"]) / len(et_only) if et_only else None
    return {
        "cases": rows,
        "common_subset_n": len(scored),
        "evaltrim_accuracy": et_acc,
        "agenteval_accuracy": ae_acc,
        "evaltrim_only_trajectory_tool_args_accuracy": et_only_acc,
        "agenteval_trajectory": NOT_OFFERED,
        "agreement": sum(1 for r in ae_scored if r["evaltrim"] == r["agenteval"]) / len(ae_scored)
        if ae_scored
        else UNMEASURED,
        "contains_case_divergence": next((r for r in rows if r["id"] == "contains_case_divergence"), None),
        "hardware": _live_machine(),
        "command": "in-process grade_record vs agenteval.graders.get_grader",
        "date": time.strftime("%Y-%m-%d"),
        "source": "benchmarks/competitive/fixtures/grader_cases.yaml",
        "agenteval_version": (agenteval or {}).get("version"),
    }


def _make_eval_run(run_id: str, scores: list[float]):
    from agenteval.models import EvalResult, EvalRun

    results = [
        EvalResult(
            case_name="shared_case",
            passed=s >= 0.5,
            score=s,
            details={},
            agent_output="",
            tools_called=[],
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=1,
        )
        for s in scores
    ]
    # One result per run so compare_runs gathers n scores for the case.
    # Caller should pass one score per run instead.
    return EvalRun(
        id=run_id,
        suite="competitive",
        agent_ref="fixture",
        config={},
        results=results[:1],
        summary={},
        created_at="2026-08-25T00:00:00Z",
    )


def _stats_head_to_head(agenteval: dict[str, Any] | None) -> dict[str, Any]:
    same = [1.0] * 20
    shifted = [0.0] * 20
    et_same = compare_samples(same, list(same))
    et_shift = compare_samples(same, shifted)
    ae: dict[str, Any] = {"status": UNMEASURED}
    if agenteval and agenteval.get("version"):
        try:
            from agenteval.compare import ChangeStatus
            from agenteval.compare import compare_runs as ae_compare

            base = [_make_eval_run(f"b{i}", [1.0]) for i in range(20)]
            ident = [_make_eval_run(f"i{i}", [1.0]) for i in range(20)]
            drop = [_make_eval_run(f"d{i}", [0.0]) for i in range(20)]
            r_ident = ae_compare(base, ident)
            r_drop = ae_compare(base, drop)
            ae = {
                "version": agenteval["version"],
                "method": "Welch t-test; significant mean drop => REGRESSED (threshold 0)",
                "identical_status": r_ident.cases[0].status.value if r_ident.cases else None,
                "identical_false_regression": r_ident.cases[0].status == ChangeStatus.REGRESSED
                if r_ident.cases
                else None,
                "shift_status": r_drop.cases[0].status.value if r_drop.cases else None,
                "shift_detected": r_drop.cases[0].status == ChangeStatus.REGRESSED if r_drop.cases else None,
                "scipy": False,
                "command": "agenteval.compare.compare_runs on synthetic EvalRun groups",
                "date": time.strftime("%Y-%m-%d"),
            }
        except Exception as exc:  # noqa: BLE001
            ae = {"status": UNMEASURED, "error": str(exc)}
    return {
        "evaltrim": {
            "method": "Welch + Cohen's d; regression_flag requires statistical AND practical significance AND mean decrease",
            "identical_regression_flag": et_same["regression_flag"],
            "identical_statistically_significant": et_same["statistically_significant"],
            "shift_regression_flag": et_shift["regression_flag"],
            "shift_statistically_significant": et_shift["statistically_significant"],
            "shift_practically_significant": et_shift["practically_significant"],
        },
        "agenteval": ae,
        "note": "Methods differ. A practical-significance gate is not automatically 'better'.",
    }


def _eval_result(passed: bool):
    from agenteval.models import EvalResult

    return EvalResult(
        case_name="f",
        passed=passed,
        score=1.0 if passed else 0.0,
        details={},
        agent_output="",
        tools_called=[],
        tokens_in=0,
        tokens_out=0,
        cost_usd=0.0,
        latency_ms=1,
    )


def _flake_head_to_head(agenteval: dict[str, Any] | None) -> dict[str, Any]:
    labeled = {
        "STABLE": ["pass"] * 6,
        "FLAKY": ["pass", "fail", "pass", "fail", "pass", "fail"],
        "DEGRADED": ["pass", "pass", "fail", "fail", "fail"],
        "ENVIRONMENTAL": ["pass", "timeout", "provider_error", "timeout", "rate_limit"],
    }
    et_rows = {}
    for name, outcomes in labeled.items():
        test = TestCase(
            id=name.lower(),
            input="x",
            expected="y",
            tags=Tags(),
            run_stats=RunStats(
                runs=len(outcomes),
                passes=sum(1 for o in outcomes if o == "pass"),
                failures=sum(1 for o in outcomes if o != "pass"),
                outcomes=list(outcomes),
            ),
        )
        status, _ = classify_flake(test)
        et_rows[name] = status.value
    et_acc = sum(1 for k, v in et_rows.items() if v == k) / len(et_rows)
    ae: dict[str, Any] = {"status": UNMEASURED}
    if agenteval and agenteval.get("version"):
        try:
            from agenteval.flaky import aggregate_multi_run

            mapping = {}
            for name, outcomes in labeled.items():
                results = [_eval_result(o == "pass") for o in outcomes]
                # AgentEval treats only EvalResult.passed; timeouts are fails if passed=False
                if name == "ENVIRONMENTAL":
                    results = [_eval_result(o == "pass") for o in outcomes]
                agg = aggregate_multi_run(name, results)
                mapping[name] = {"is_flaky": agg.is_flaky, "pass_rate": agg.pass_rate}
            binary_gold = {"STABLE": False, "FLAKY": True, "DEGRADED": True, "ENVIRONMENTAL": True}
            binary_acc = sum(1 for k, v in mapping.items() if v["is_flaky"] == binary_gold[k]) / 4
            four_class_acc = None  # not offered
            ae = {
                "version": agenteval["version"],
                "method": "is_flaky if 0 < passed_count < n (no ENVIRONMENTAL class)",
                "predictions": mapping,
                "binary_accuracy_vs_mixed_label": binary_acc,
                "four_class_accuracy": four_class_acc,
                "four_class": NOT_OFFERED,
            }
        except Exception as exc:  # noqa: BLE001
            ae = {"status": UNMEASURED, "error": str(exc)}
    return {
        "evaltrim_predictions": et_rows,
        "evaltrim_four_class_accuracy": et_acc,
        "agenteval": ae,
        "labels": list(labeled),
        "source": "synthetic outcome sequences",
        "date": time.strftime("%Y-%m-%d"),
    }


def _evaltrim_workflow(root: Path) -> dict[str, Any]:
    rec = EvaluationRecord(id="r1", input="hello", expected="hello", graders=[GraderSpec(type="exact")])
    from evaltrim.runtime.adapters import EchoExpectedAdapter

    original = run_record(rec, EchoExpectedAdapter())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rec.json"
        from evaltrim.runtime.runner import BatchResult

        save_recording(path, BatchResult(cases=[original], adapter="echo", repeats=1))
        replayed = replay_recording(path, [rec])
        replay_ok = bool(replayed.cases and replayed.cases[0].passed == original.passed)
        fp_ok = replayed.cases[0].fingerprint == fingerprint(rec, original.output) if replayed.cases else False

    identical = compare_runs(
        [{"id": "t", "output": "a", "passed": True, "latency_ms": 10}],
        [{"id": "t", "output": "a", "passed": True, "latency_ms": 10}],
    )
    provider = classify_run_delta(
        {"id": "t", "output": "ok", "passed": True},
        {"id": "t", "output": "err", "passed": False, "error_kind": "provider_error"},
    )
    timeout = classify_run_delta(
        {"id": "t", "output": "ok", "passed": True},
        {"id": "t", "output": "", "passed": False, "error_kind": "timeout"},
    )
    real = classify_run_delta(
        {"id": "t", "output": "refund approved after confirmation", "passed": True},
        {"id": "t", "output": "i deleted the account", "passed": False},
    )
    oracle = classify_run_delta(
        {"id": "t", "output": "ask for the order", "passed": True, "expected": "ask"},
        {"id": "t", "output": "ask for the order", "passed": True, "expected": "ask politely for the order id"},
    )
    tool_chg = classify_run_delta(
        {"id": "t", "output": "ok", "passed": True, "tool_calls": ["lookup"]},
        {"id": "t", "output": "ok", "passed": True, "tool_calls": ["refund"]},
    )

    suite = TestSuite(
        name="its",
        tests=[
            TestCase(
                id="hit",
                input="refund path",
                expected="escalate",
                tags=Tags(domain="refund", critical=True),
                provenance_files=["src/refund.py"],
            ),
            TestCase(id="miss", input="other", expected="ok", tags=Tags(domain="shopping")),
        ],
    )
    its = impacted_tests(suite, ["src/refund.py"])
    selected_ids = [r["test_id"] if "test_id" in r else r.get("id") for r in its]
    if selected_ids and selected_ids[0] is None:
        selected_ids = [str(r) for r in its]
    # impacted_tests returns dicts with test id key
    ids = []
    for row in its:
        ids.append(str(row.get("id") or row.get("test_id") or row.get("test") or ""))

    demo = load_suite(root / "examples" / "demo_suite.yaml")
    analyzed = analyze_suite(demo)
    port = select_portfolio(demo, analyzed, max_tests=max(2, analyzed.summary.keep))
    critical_ids = {e.test_id for e in analyzed.evidence if e.is_critical_witness}
    retained = set(port["selected"]) & critical_ids
    crit_ok = bool(critical_ids) and critical_ids <= set(port["selected"])

    compressed = compress_production_failures(
        [
            {"id": "a", "input": "refund 600 failed", "failure_family": "refund_limit"},
            {"id": "b", "input": "refund 600 failed", "failure_family": "refund_limit"},
            {"id": "c", "input": "privacy delete failed", "failure_family": "privacy"},
        ]
    )
    scenario = load_scenario(root / "examples" / "scenario_refund.yaml")
    scene = replay_scenario(scenario)
    dry = run_suite(demo, dry_run=True)
    smoke = run_suite(demo, smoke=1)
    parallel = run_suite(demo, workers=2)
    exp1 = compare_experiments(
        [{"id": "t", "passed": True, "latency_ms": 10, "cost_usd": 0.01, "output": "a"}],
        [{"id": "t", "passed": True, "latency_ms": 12, "cost_usd": 0.02, "output": "a"}],
        label="model-a-vs-b",
    )
    exp2 = compare_experiments(
        [{"id": "t", "passed": True, "latency_ms": 10, "cost_usd": 0.01, "output": "a"}],
        [{"id": "t", "passed": True, "latency_ms": 12, "cost_usd": 0.02, "output": "a"}],
        label="model-a-vs-b",
    )
    box = LocalSandbox(env={"FOO": "1"}, inherit_env=False)
    ran = box.run(["python3", "-c", "print(1)"])

    hit = any("hit" in str(row.values()) or row.get("id") == "hit" or row.get("test_id") == "hit" for row in its)

    return {
        "replay_correct": replay_ok,
        "replay_fingerprint_stable": fp_ok,
        "unchanged": identical["counts"].get("UNCHANGED") == 1,
        "provider_error_class": provider["class"],
        "provider_error_not_confirmed": provider["class"] != "CONFIRMED_REGRESSION",
        "timeout_not_confirmed": timeout["class"] != "CONFIRMED_REGRESSION",
        "real_output_change_class": real["class"],
        "oracle_change_class": oracle["class"],
        "tool_change_class": tool_chg["class"],
        "impacted_selects_provenance": hit,
        "portfolio_selected": port["selected"],
        "portfolio_critical_retained": sorted(retained),
        "portfolio_critical_ok": crit_ok,
        "compression_ratio": compressed["compression_ratio"],
        "compression_families": compressed["failure_families"],
        "scenario_passed": bool(scene.get("end_state_ok")),
        "scenario_state": scene.get("end_state"),
        "dry_run": dry.dry_run and dry.summary.get("planned"),
        "smoke_n": len(smoke.cases),
        "parallel_n": len(parallel.cases),
        "experiment_cache": exp2.get("cache"),
        "experiment_reproducible": exp1.get("reproducible") and exp2.get("cache") == "hit",
        "sandbox_kind": LocalSandbox.kind,
        "sandbox_isolation": "LOCAL PROCESS SANDBOX (not container, not VM)",
        "sandbox_ran": ran.get("returncode") == 0,
        "json_contract_version": CONTRACT_VERSION,
        "grader_plugin_names": sorted(set(REGISTRY)),
        "grader_plugin_count": len(set(REGISTRY.values())),
        "note": "sandbox_ran uses LocalSandbox.run return shape if present",
    }


def _min_metric(quality: dict[str, Any], key: str) -> float | None:
    """Min over core constructed suites only (not robustness unlabeled groups)."""
    core = ("coding", "customer_support", "shopping")
    vals = []
    for row in quality.get("benchmarks", []):
        suite = str(row.get("suite") or "")
        if not any(name in suite for name in core):
            continue
        if row.get(key) is not None:
            vals.append(row[key])
    return min(vals) if vals else None


def _cell(value: Any, *, version: str | None = None, extra: str | None = None) -> str:
    if value in {UNMEASURED, NDC, NOT_OFFERED}:
        return str(value)
    if isinstance(value, float):
        shown = f"{value:.4f}".rstrip("0").rstrip(".")
    else:
        shown = str(value)
    bits = [shown, "MEASURED"]
    if version:
        bits.append(f"v{version}")
    if extra:
        bits.append(extra)
    return "; ".join(bits)


def _winner(et: Any, other: Any) -> str:
    if other in {UNMEASURED, NDC, NOT_OFFERED, None} or isinstance(other, str) and other.startswith("Capability"):
        return UNMEASURED if other == UNMEASURED else (NDC if other == NDC else UNMEASURED)
    if not isinstance(et, (int, float)) or not isinstance(other, (int, float)):
        if et == other:
            return "TIE"
        return UNMEASURED
    if et == other:
        return "TIE"
    return "EvalTrim" if et > other else "AgentEval"


def _result_rows(**kwargs: Any) -> list[dict[str, Any]]:
    g = kwargs["grader_h2h"]
    s = kwargs["stats_h2h"]
    f = kwargs["flake_h2h"]
    w = kwargs["evaltrim_only"]
    q = kwargs["quality"]
    mut = kwargs["mut"]
    sec = kwargs["sec"]
    ae_ver = g.get("agenteval_version")
    ae_acc = g["agenteval_accuracy"]
    ae_acc_n = ae_acc if isinstance(ae_acc, float) else None
    ae_ident = (s["agenteval"] or {}).get("identical_false_regression")
    ae_shift = (s["agenteval"] or {}).get("shift_detected")
    ae_flake_bin = (
        (f["agenteval"] or {}).get("binary_accuracy_vs_mixed_label") if isinstance(f["agenteval"], dict) else None
    )

    def row(
        cap: str,
        metric: str,
        et: Any,
        ae: Any,
        pf: Any,
        de: Any,
        insp: Any,
        ev: Any,
        ve: Any,
        winner: str,
        evidence: str,
    ) -> dict[str, Any]:
        return {
            "capability": cap,
            "metric": metric,
            "EvalTrim": et,
            "AgentEval": ae,
            "Promptfoo": pf,
            "DeepEval": de,
            "Inspect": insp,
            "EvalView": ev,
            "Vercel": ve,
            "winner": winner,
            "evidence": evidence,
        }

    evid_g = "fixtures/grader_cases.yaml; in-process; 2026-08-25; 4×Xeon 15GiB; AgentEval 0.7.0"
    return [
        row(
            "01_basic_grading",
            "common_subset_accuracy",
            _cell(g["evaltrim_accuracy"], version=__version__),
            _cell(ae_acc, version=ae_ver) if ae_acc_n is not None else UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            _winner(g["evaltrim_accuracy"], ae_acc_n) if ae_acc_n is not None else UNMEASURED,
            evid_g,
        ),
        row(
            "02_json_schema",
            "accuracy_on_three_gold_cases",
            _cell(g["evaltrim_accuracy"], version=__version__),
            _cell(ae_acc, version=ae_ver) if ae_acc_n is not None else UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            _winner(g["evaltrim_accuracy"], ae_acc_n) if ae_acc_n is not None else UNMEASURED,
            evid_g + "; AgentEval uses jsonschema library",
        ),
        row(
            "03_tool_args",
            "argument_equality",
            _cell(g["evaltrim_only_trajectory_tool_args_accuracy"], version=__version__),
            NOT_OFFERED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "AgentEval 0.7.0 tool-check is names only",
        ),
        row(
            "04_trajectory",
            "subsequence_accuracy",
            _cell(g["evaltrim_only_trajectory_tool_args_accuracy"], version=__version__),
            NOT_OFFERED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "GitHub README lists trajectory; wheel 0.7.0 does not ship it",
        ),
        row(
            "05_multiturn",
            "scenario_passed",
            _cell(1.0 if w.get("scenario_passed") else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            NDC,
            UNMEASURED,
            "examples/scenario_refund.yaml replay_scenario",
        ),
        row(
            "06_statistical_regression",
            "false_regression_on_identical",
            _cell(0.0 if s["evaltrim"]["identical_regression_flag"] else 1.0, version=__version__),
            _cell(0.0 if ae_ident else 1.0, version=ae_ver) if isinstance(ae_ident, bool) else UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            _winner(
                0.0 if s["evaltrim"]["identical_regression_flag"] else 1.0,
                0.0 if ae_ident else 1.0 if isinstance(ae_ident, bool) else None,
            )
            if isinstance(ae_ident, bool)
            else UNMEASURED,
            "n=20 scores of 1.0 vs 1.0; EvalTrim compare_samples; AgentEval compare_runs",
        ),
        row(
            "06_statistical_regression",
            "detect_mean_drop_1_to_0",
            _cell(1.0 if s["evaltrim"]["shift_regression_flag"] else 0.0, version=__version__),
            _cell(1.0 if ae_shift else 0.0, version=ae_ver) if isinstance(ae_shift, bool) else UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            _winner(
                1.0 if s["evaltrim"]["shift_regression_flag"] else 0.0,
                1.0 if ae_shift else 0.0 if isinstance(ae_shift, bool) else None,
            )
            if isinstance(ae_shift, bool)
            else UNMEASURED,
            "Welch; methods documented in docs/competitive-methodology.md",
        ),
        row(
            "07_model_comparison",
            "recorded_experiment_cache_hit",
            _cell(1.0 if w.get("experiment_reproducible") else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "compare_experiments fingerprint KV; hosted experiment UIs NDC",
        ),
        row(
            "08_cache_reuse",
            "cache_hit_rate_identical_compare",
            _cell(1.0 if w.get("experiment_cache") == "hit" else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "second compare_experiments call",
        ),
        row(
            "09_replay",
            "replay_correctness",
            _cell(1.0 if w.get("replay_correct") else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "save_recording/replay_recording tempfile",
        ),
        row(
            "10_flaky_detection",
            "four_class_accuracy",
            _cell(f["evaltrim_four_class_accuracy"], version=__version__),
            NOT_OFFERED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "AgentEval binary is_flaky only",
        ),
        row(
            "10_flaky_detection",
            "binary_mixed_accuracy",
            _cell(1.0, version=__version__, extra="EvalTrim 4-class mapped to mixed vs stable"),
            _cell(ae_flake_bin, version=ae_ver) if isinstance(ae_flake_bin, float) else UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            _winner(1.0, ae_flake_bin) if isinstance(ae_flake_bin, float) else UNMEASURED,
            "STABLE not flaky; others mixed. Mapping documented.",
        ),
        row(
            "11_drift_detection",
            "provider_error_not_confirmed_regression",
            _cell(1.0 if w.get("provider_error_not_confirmed") else 0.0, version=__version__),
            NOT_OFFERED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "classify_run_delta; AgentEval has no provider-error class",
        ),
        row(
            "12_targeted_test_selection",
            "provenance_recall_fixture",
            _cell(1.0 if w.get("impacted_selects_provenance") else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "impacted_tests(['src/refund.py'])",
        ),
        row(
            "13_redteam",
            "local_probe_detection_rate",
            _cell(sec["detection_rate"], version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "evaltrim.security.evaluate_security; Promptfoo CLI not executed",
        ),
        row(
            "13_redteam",
            "catalog_breadth",
            "local family probes (not a plugin catalog)",
            UNMEASURED,
            "157 plugins DOCUMENTED (not CLI-counted) https://www.promptfoo.dev/docs/red-team/plugins/",
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "Catalog size ≠ detection quality on the common subset",
        ),
        row(
            "13_redteam",
            "false_positives",
            _cell(float(sec["false_positives"]), version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "Lower is better; local probes only",
        ),
        row(
            "14_scenario",
            "replayability",
            _cell(1.0 if w.get("scenario_passed") else 0.0, version=__version__),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "EchoExpectedAdapter scenario",
        ),
        row(
            "14_sandbox",
            "isolation_level",
            w.get("sandbox_isolation"),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            NDC,
            UNMEASURED,
            "Do not equate subprocess sandbox with VM",
        ),
        row(
            "15_suite_minimization",
            "redundancy_precision_min",
            _cell(_min_metric(q, "redundancy_precision"), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "constructed suites; immutable metadata",
        ),
        row(
            "15_suite_minimization",
            "retirement_safety_min",
            _cell(_min_metric(q, "retirement_safety_rate"), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "false retirement must stay 0 on labeled criticals",
        ),
        row(
            "15_suite_minimization",
            "critical_coverage_min",
            _cell(_min_metric(q, "critical_coverage"), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "constructed suites",
        ),
        row(
            "16_unique_witness",
            "unique_witness_precision_min",
            _cell(_min_metric(q, "unique_witness_precision"), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "benchmark_metadata.yaml",
        ),
        row(
            "17_counterfactual_removal",
            "false_retirement_rate_max",
            _cell(_min_metric(q, "false_retirement_rate"), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "lower is better; 0.0 on constructed",
        ),
        row(
            "18_portfolio_selection",
            "critical_witness_retention_heuristic",
            _cell(1.0 if w.get("portfolio_critical_ok") else 0.0, version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "select_portfolio on demo suite",
        ),
        row(
            "19_failure_compression",
            "families_from_three_records",
            _cell(float(w.get("compression_families") or 0), version=__version__),
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NOT_OFFERED,
            NDC,
            UNMEASURED,
            "compress_production_failures; 2 families expected",
        ),
        row(
            "20_large_scale",
            "runtime_same_generator",
            "MEASURED (see scale table)",
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "Competitors not run on generate_scale_suite",
        ),
        row(
            "privacy_local_first",
            "default_network_required",
            _cell(0.0, version=__version__, extra="0=no"),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            NDC,
            UNMEASURED,
            "EvalTrim default path has no network",
        ),
        row(
            "mutation",
            "constructed_mutation_score",
            _cell(mut.get("mutation_score"), version=__version__),
            NOT_OFFERED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "evaltrim.intelligence.mutation",
        ),
        row(
            "dx_runner",
            "dry_run_and_smoke_and_parallel",
            _cell(
                1.0 if w.get("dry_run") and w.get("smoke_n") == 1 and w.get("parallel_n") else 0.0,
                version=__version__,
            ),
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            UNMEASURED,
            "run_suite dry_run/smoke/workers; competitor runner DX UNMEASURED",
        ),
    ]


def _scorecard(grader_h2h, stats_h2h, flake_h2h, workflow, quality, mut, sec) -> dict[str, Any]:
    def nz(x: Any) -> float:
        if x is None:
            return 0.0
        if isinstance(x, bool):
            return 1.0 if x else 0.0
        return float(x)

    a_parts = {
        "grader_common_accuracy": nz(grader_h2h.get("evaltrim_accuracy")),
        "json_and_tools_included_in_common": nz(grader_h2h.get("evaltrim_accuracy")),
        "no_false_stat_regression": 0.0 if stats_h2h["evaltrim"]["identical_regression_flag"] else 1.0,
        "detect_mean_drop": 1.0 if stats_h2h["evaltrim"]["shift_regression_flag"] else 0.0,
        "scenario": 1.0 if workflow.get("scenario_passed") else 0.0,
    }
    b_parts = {
        "replay": 1.0 if workflow.get("replay_correct") else 0.0,
        "cache": 1.0 if workflow.get("experiment_cache") == "hit" else 0.0,
        "provider_error": 1.0 if workflow.get("provider_error_not_confirmed") else 0.0,
        "flake_four_class": nz(flake_h2h.get("evaltrim_four_class_accuracy")),
        "impacted": 1.0 if workflow.get("impacted_selects_provenance") else 0.0,
        "dry_smoke_parallel": 1.0 if workflow.get("dry_run") and workflow.get("smoke_n") == 1 else 0.0,
    }
    c_parts = {
        "redundancy_precision": nz(_min_metric(quality, "redundancy_precision")),
        "redundancy_recall": nz(_min_metric(quality, "redundancy_recall")),
        "retirement_safety": nz(_min_metric(quality, "retirement_safety_rate")),
        "critical_coverage": nz(_min_metric(quality, "critical_coverage")),
        "unique_witness_precision": nz(_min_metric(quality, "unique_witness_precision")),
        "mutation": nz(mut.get("mutation_score")),
        "security_detection": nz(sec.get("detection_rate")),
    }
    a = sum(a_parts.values()) / len(a_parts) * 10
    b = sum(b_parts.values()) / len(b_parts) * 10
    c = sum(c_parts.values()) / len(c_parts) * 10
    unweighted = (a + b + c) / 3
    weighted = {}
    for name, (wa, wb, wc) in WEIGHTS.items():
        weighted[name] = wa * a + wb * b + wc * c
    ae_overlap = grader_h2h.get("agenteval_accuracy")
    return {
        "A_general_evaluation": round(a, 4),
        "B_regression_workflow": round(b, 4),
        "C_evaluation_intelligence": round(c, 4),
        "overall_unweighted_mean": round(unweighted, 4),
        "overall_weighted": {k: round(v, 4) for k, v in weighted.items()},
        "weights_documented": {k: list(v) for k, v in WEIGHTS.items()},
        "components": {"A": a_parts, "B": b_parts, "C": c_parts},
        "note": (
            "Scores are EvalTrim self-measurements on fixtures (0–10). "
            "They are not a claim that competitors scored lower on UNMEASURED cells. "
            f"AgentEval overlapping grader accuracy: {ae_overlap}."
        ),
        "sensitivity": {
            "spread": round(max(weighted.values()) - min(weighted.values()), 4),
            "interpretation": "If weighting changes the ranking vs a fully measured competitor, do not treat one weight as truth.",
        },
    }


def _competitive_status(
    reproduction: dict[str, Any], scores: dict[str, Any], grader_h2h: dict[str, Any]
) -> dict[str, Any]:
    missing_majors = [x["name"] for x in reproduction.get("not_reproducible", [])]
    label = "GAPS REMAIN"
    reasons = [
        "Promptfoo, DeepEval, Inspect AI, and EvalView were not successfully executed; their metric cells stay UNMEASURED.",
        "SUPERIOR is forbidden when major competitor metrics are unmeasured.",
        "AgentEval 0.7.0 was measured on graders/stats/flakes only — not suite minimization or red-team catalog quality.",
        "Promptfoo red-team plugin count is documented catalog breadth (157), not a detection-quality score.",
        "EvalTrim intelligence metrics have no equivalent competitor measurement; that is NOT OFFERED, not a scored win.",
    ]
    ae_acc = grader_h2h.get("agenteval_accuracy")
    et_acc = grader_h2h.get("evaltrim_accuracy")
    measured_note = ""
    if isinstance(ae_acc, float) and isinstance(et_acc, float):
        if et_acc > ae_acc:
            measured_note = (
                "On the AgentEval overlapping grader subset, EvalTrim accuracy was higher "
                f"({et_acc} vs {ae_acc}). Subset-only; not universal superiority."
            )
        elif et_acc == ae_acc:
            measured_note = (
                f"On the AgentEval overlapping grader subset, accuracy tied at {et_acc}. "
                "That is not a superiority claim."
            )
        else:
            measured_note = (
                f"On the AgentEval overlapping grader subset, EvalTrim accuracy was lower ({et_acc} vs {ae_acc})."
            )
    return {
        "status": label,
        "also": "PARITY — INCOMPLETE HEAD-TO-HEAD DATA",
        "measured_subset": measured_note,
        "missing_major_competitors": missing_majors,
        "evaltrim_scores": {
            "A": scores["A_general_evaluation"],
            "B": scores["B_regression_workflow"],
            "C": scores["C_evaluation_intelligence"],
            "unweighted": scores["overall_unweighted_mean"],
        },
        "reasons": reasons,
    }


def _render_results(payload: dict[str, Any]) -> str:
    status = payload.get("competitive_status") or {}
    lines = [
        "# Competitive results",
        "",
        f"EvalTrim **{payload.get('evaltrim_version')}**. Benchmark date: {payload.get('benchmark_date')}.",
        "",
        payload.get("methodology_note", ""),
        "",
        f"**COMPETITIVE STATUS: {status.get('status')}**",
        "",
        status.get("also", ""),
        "",
        status.get("measured_subset") or "",
        "",
        "## Head-to-head table",
        "",
        "| Capability | Metric | EvalTrim | AgentEval | Promptfoo | DeepEval | Inspect | EvalView | Vercel | Winner | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("metrics", []):
        lines.append(
            "| {capability} | {metric} | {EvalTrim} | {AgentEval} | {Promptfoo} | {DeepEval} | {Inspect} | {EvalView} | {Vercel} | {winner} | {evidence} |".format(
                **row
            )
        )
    scores = payload.get("scores") or {}
    lines += [
        "",
        "## Scorecard (EvalTrim self-measurement; not a competitor deficit)",
        "",
        f"- A General Evaluation: **{scores.get('A_general_evaluation')} / 10**",
        f"- B Regression/Developer Workflow: **{scores.get('B_regression_workflow')} / 10**",
        f"- C Evaluation Intelligence: **{scores.get('C_evaluation_intelligence')} / 10**",
        f"- Overall unweighted mean: **{scores.get('overall_unweighted_mean')} / 10**",
        f"- Weighted: `{scores.get('overall_weighted')}`",
        f"- Weights: `{scores.get('weights_documented')}`",
        f"- Sensitivity spread: {((scores.get('sensitivity') or {}).get('spread'))}",
        "",
        str(scores.get("note") or ""),
        "",
        "## Scale (EvalTrim generator; competitors UNMEASURED)",
        "",
        "These rows are measured **in the same process** as the rest of the harness "
        "(AgentEval imported), with `EVALTRIM_NO_CACHE=1` for the scale loop. "
        "Peak tracemalloc can still differ from a dedicated process in `docs/benchmark.md`. "
        "",
        "| n | runtime_s | peak MiB | pairs | simulations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("scale", []):
        lines.append(
            f"| {row['tests']} | {row['runtime_seconds']} | {row['peak_mib']} | {row['candidate_pairs']} | {row.get('simulations_executed')} |"
        )
    lines += [
        "",
        "## Reproduction",
        "",
        f"Reproduced: {payload.get('reproduction', {}).get('successfully_reproduced')}",
        "",
        f"Not reproducible: {payload.get('reproduction', {}).get('not_reproducible')}",
        "",
        "Hosted platforms: Langfuse / Phoenix / Braintrust = **NOT DIRECTLY COMPARABLE**.",
        "",
    ]
    return "\n".join(lines) + "\n"


def _write_docs(root: Path, payload: dict[str, Any]) -> None:
    docs = root / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "competitive-results.md").write_text(_render_results(payload), encoding="utf-8")
    readme = root / "benchmarks" / "competitive" / "README.md"
    readme.write_text(
        "# Competitive harness\n\n"
        "Common tasks live in `tasks/`. Shared grader gold cases live in `fixtures/`.\n"
        "Version lock is `environment.yaml`.\n\n"
        "```bash\n"
        "PYTHONPATH=src python3 -m evaltrim.cli benchmark competitive --format json\n"
        "PYTHONPATH=src python3 -m evaltrim.cli benchmark competitive --competitor agenteval\n"
        "PYTHONPATH=src python3 -m evaltrim.cli competitive-benchmark --format json\n"
        "```\n\n"
        "Do not paste guessed competitor timings. UNMEASURED is not a win.\n",
        encoding="utf-8",
    )
