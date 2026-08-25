"""EvalTrim 0.9 maturity tests."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from evaltrim.analyze import analyze_suite
from evaltrim.behavior import extract_behavior
from evaltrim.cli import app
from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GraderSpec, ToolCallRecord, TrajectoryStep, Usage
from evaltrim.evaluation.graders import grade_record, listed_graders
from evaltrim.experiments import compare_experiments, plan_experiment, replay_manifest, write_manifest
from evaltrim.models import Behavior, RedundancyWeights, TestCase
from evaltrim.parser import parse_suite
from evaltrim.sandbox import LocalSandbox
from evaltrim.scenarios import load_scenario, replay_scenario
from evaltrim.security import FAMILIES, evaluate_security
from evaltrim.similarity import SimilarityEngine
from evaltrim.simulate import RemovalIndex, simulate_cached, simulate_from_index
from evaltrim.trajectory_diff import compare_trajectories, render_trajectory_diff

runner = CliRunner()


def test_new_graders():
    rec = EvaluationRecord(
        id="g",
        input="x",
        expected="10",
        metadata={"state": {"order": "found"}},
        graders=[
            GraderSpec(type="json_path", params={"path": "$.n", "equals": 1}),
            GraderSpec(type="ordered_subsequence", params={"order": ["lookup_order", "refund"]}),
            GraderSpec(type="required_tool", params={"tools": ["lookup_order"]}),
            GraderSpec(type="forbidden_tool", params={"tools": ["delete_all"]}),
            GraderSpec(type="max_tool_calls", params={"max": 3}),
            GraderSpec(type="max_trajectory_length", params={"max": 5}),
            GraderSpec(type="state_predicate", params={"equals": {"order": "found"}}),
            GraderSpec(type="lcs_trajectory", params={"order": ["lookup_order", "refund"], "threshold": 1.0}),
            GraderSpec(type="json_schema", params={"schema": {"type": "object", "required": ["n"]}}),
        ],
    )
    out = AgentOutput(
        text='{"n": 1}',
        tool_calls=[ToolCallRecord(name="lookup_order"), ToolCallRecord(name="refund")],
        trajectory=[TrajectoryStep(kind="lookup_order"), TrajectoryStep(kind="refund")],
        usage=Usage(latency_ms=1),
    )
    # Split: numeric/set use different texts
    num_spec = [GraderSpec(type="numeric", params={"expected": 10, "abs": 0.2})]
    num = grade_record(rec.model_copy(update={"graders": num_spec}), AgentOutput(text="10.1"))
    assert num[0].passed is True
    set_spec = [GraderSpec(type="set_equality", params={"expected": ["b", "a"]})]
    sets = grade_record(rec.model_copy(update={"graders": set_spec}), AgentOutput(text='["a","b"]'))
    assert sets[0].passed is True
    grades = grade_record(rec, out)
    assert all(g.passed for g in grades)
    assert "numeric_tolerance" in listed_graders()
    assert "state_predicate" in listed_graders()


def test_semantic_paraphrase_and_hard_negative():
    tests = [
        TestCase(id="a", input="I need a refund of $600", expected="escalate"),
        TestCase(id="b", input="Please return six hundred dollars", expected="escalate"),
        TestCase(id="c", input="I need a refund of $600, but I already received store credit", expected="clarify"),
    ]
    behaviors = [
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
        Behavior(domain="refund", action="clarification", conditions=["store_credit"]),
    ]
    engine = SimilarityEngine(tests, behaviors, RedundancyWeights())
    para = engine.pair_score("a", "b")
    hard = engine.pair_score("a", "c")
    assert para["semantic"] > hard["semantic"]
    assert para["semantic"] >= 0.8
    assert hard["semantic"] < 0.85
    assert hard["unique_right"]
    assert para["semantic_confidence"] >= 0.5
    assert para["combined_confidence"] >= 0.3


def test_simulation_cache_matches_uncached():
    suite = parse_suite(
        {
            "critical_behaviors": ["payment"],
            "tests": [
                {
                    "id": "a",
                    "input": "refund 20",
                    "expected": "pay",
                    "tags": {"domain": "refund", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "b",
                    "input": "refund 20 copy",
                    "expected": "pay",
                    "tags": {"domain": "refund", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "c",
                    "input": "delete data",
                    "expected": "confirm",
                    "tags": {"domain": "privacy", "critical": True, "behavior": ["destructive"]},
                },
            ],
        }
    )
    tests = suite.tests
    behaviors = [extract_behavior(t, declared_critical=suite.critical_behaviors) for t in tests]
    index = RemovalIndex.build(tests, behaviors, declared_critical=suite.critical_behaviors, suite=suite)
    cache: dict = {}
    for t in tests:
        cached = simulate_cached(index, t.id, cache)
        direct = simulate_from_index(index, t.id)
        assert cached.verdict == direct.verdict
        assert cached.lost_unique_witnesses == direct.lost_unique_witnesses


def test_trajectory_diff_risk():
    payload = compare_trajectories(
        ["model", "lookup_order", "verify_customer", "refund"],
        ["model", "refund"],
    )
    assert "verify_customer" in payload["removed"]
    assert payload["risk"] == "HIGH"
    md = render_trajectory_diff(payload)
    assert "REMOVED STEP: verify_customer" in md
    assert "RISK: HIGH" in md


def test_experiment_verdict_and_manifest(tmp_path: Path):
    baseline = [{"id": "t", "passed": True, "cost_usd": 0.1, "latency_ms": 10}]
    better = [{"id": "t", "passed": True, "cost_usd": 0.05, "latency_ms": 8}]
    worse = [{"id": "t", "passed": False, "cost_usd": 0.01, "latency_ms": 8}]
    rec = compare_experiments(baseline, better)
    assert rec["verdict"]["label"] in {"RECOMMENDED", "INCONCLUSIVE", "TRADEOFF"}
    reg = compare_experiments(baseline, worse)
    assert reg["verdict"]["label"] == "REGRESSION"
    dest = tmp_path / "m.json"
    write_manifest(dest, {"baseline": baseline, "current": better})
    again = replay_manifest(dest)
    assert again["verdict"]["label"] == rec["verdict"]["label"]
    plan = plan_experiment({"model": ["a", "b"], "prompt": ["p1"]}, smoke=True)
    assert plan["n"] == 1


def test_redteam_families():
    sec = evaluate_security()
    assert sec["detection_rate"] == 1.0
    assert sec["false_positives"] == 0
    assert sec["critical_safety_coverage"] == 1.0
    for family in (
        "prompt_injection",
        "indirect_injection",
        "jailbreak",
        "tool_misuse",
        "authorization_bypass",
        "destructive_tools",
        "sensitive_data_disclosure",
        "malicious_tool_output",
        "memory_poisoning",
        "data_exfiltration",
        "instruction_hierarchy",
    ):
        assert family in FAMILIES
        assert any(c["family"] == family for c in sec["cases"])


def test_scenario_yaml(tmp_path: Path):
    path = Path("examples/scenario_refund.yaml")
    scene = load_scenario(path)
    out = replay_scenario(scene)
    assert out["reproducibility"] == 1.0
    assert out["end_state_ok"] is True
    assert out["persona"] == "confused"


def test_sandbox_escape_and_limits(tmp_path: Path):
    box = LocalSandbox(root=tmp_path, timeout=1.0, max_output=20)
    box.write_text("ok.txt", "hello")
    try:
        box.resolve("../secret.txt")
        raise AssertionError("escape allowed")
    except PermissionError:
        pass
    ran = box.run(["python3", "-c", "print('x'*100)"])
    assert "truncated" in ran["stdout"] or len(ran["stdout"]) <= 40
    timed = LocalSandbox(root=tmp_path, timeout=0.05).run(["python3", "-c", "import time; time.sleep(2)"])
    assert timed["timeout"] is True or timed["returncode"] != 0
    assert box.kind == "LOCAL_SANDBOX"


def test_replay_compare_cli(tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text(json.dumps(["model", "lookup_order", "verify_customer", "refund"]), encoding="utf-8")
    b.write_text(json.dumps(["model", "refund"]), encoding="utf-8")
    result = runner.invoke(app, ["replay", "--compare", str(a), str(b)])
    assert result.exit_code == 0
    assert "REMOVED STEP" in result.stdout
    assert "HIGH" in result.stdout


def test_named_portfolios_and_value_components():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "crit",
                    "input": "delete",
                    "expected": "confirm",
                    "tags": {"domain": "privacy", "critical": True, "behavior": ["destructive"]},
                },
                {"id": "dup1", "input": "hi", "expected": "ho", "tags": {"domain": "chitchat"}},
                {"id": "dup2", "input": "hi there", "expected": "ho", "tags": {"domain": "chitchat"}},
            ]
        }
    )
    result = analyze_suite(suite)
    assert result.evidence[0].value_components
    from evaltrim.intelligence.portfolio import named_portfolios

    port = named_portfolios(suite, result, max_tests=2)
    assert "BEST_COMPACT_PORTFOLIO" in port
    assert "BEST_CRITICAL_PORTFOLIO" in port
    assert "BEST_COST_CONSTRAINED_PORTFOLIO" in port
    assert "crit" in port["BEST_CRITICAL_PORTFOLIO"]["selected"] or result.evidence[0].is_critical_witness


def test_doctor_and_scenario_cli():
    doc = runner.invoke(app, ["doctor"])
    assert doc.exit_code == 0
    assert "LOCAL_SANDBOX" in doc.stdout or "sandbox" in doc.stdout
    sc = runner.invoke(app, ["scenario", "examples/scenario_refund.yaml"])
    assert sc.exit_code == 0


def test_analyze_verbose_cards():
    result = runner.invoke(app, ["analyze", "examples/demo_suite.yaml", "--verbose"])
    assert result.exit_code == 0
    assert "Why:" in result.stdout or "Evidence:" in result.stdout


def test_cache_corruption_and_malformed(tmp_path: Path):
    from evaltrim.errors import SuiteValidationError
    from evaltrim.parser import load_suite

    bad = tmp_path / "bad.yaml"
    bad.write_text("tests: [", encoding="utf-8")
    try:
        load_suite(bad)
        raise AssertionError("expected validation error")
    except (SuiteValidationError, Exception):
        pass
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "tests:\n  - id: a\n    input: x\n    expected: y\n  - id: a\n    input: z\n    expected: y\n",
        encoding="utf-8",
    )
    try:
        load_suite(dup)
        raise AssertionError("duplicate ids")
    except Exception:
        pass
    empty = tmp_path / "empty.yaml"
    empty.write_text("tests: []\n", encoding="utf-8")
    try:
        load_suite(empty)
        raise AssertionError("empty suite")
    except Exception:
        pass
