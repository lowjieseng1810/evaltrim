"""v0.5 / v0.6 agent-native workflow, cache, doctor, defects, JSON stability."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from evaltrim.analyze import analyze_suite
from evaltrim.cache import load_cached_analysis, store_cached_analysis, suite_fingerprint
from evaltrim.cli import app
from evaltrim.constants import ANALYSIS_ALGO_VERSION
from evaltrim.doctor import doctor
from evaltrim.errors import SuiteValidationError
from evaltrim.experiments import compare_experiments
from evaltrim.explain import explain_test
from evaltrim.gate import gate
from evaltrim.impacted import impacted_tests
from evaltrim.incremental import PairScoreCache, content_hash_for_test
from evaltrim.intelligence.portfolio import select_portfolio
from evaltrim.mcp_adapter import TOOLS, dispatch
from evaltrim.models import AnalysisConfig, RecommendationState, SafetyPolicies
from evaltrim.parser import load_suite, parse_suite
from evaltrim.policy import PolicyError, load_policy_file
from evaltrim.status import project_status
from evaltrim.store import put_kv, reset_store
from evaltrim.traces import load_traces
from evaltrim.watch import debounce, watch_once

runner = CliRunner()
DEMO = Path("examples/demo_suite.yaml")


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("EVALTRIM_DB", str(tmp_path / "evaltrim.sqlite"))
    monkeypatch.delenv("EVALTRIM_NO_CACHE", raising=False)
    reset_store(tmp_path / "evaltrim.sqlite")
    yield tmp_path


def _tiny_suite(**kwargs):
    data = {
        "name": "tiny",
        "tests": [
            {
                "id": "a",
                "input": "My parcel is late, what can you do?",
                "expected": "Offer tracking help.",
                "tags": {"domain": "support", "action": "execution", "behavior": ["amount_below_limit"]},
            },
            {
                "id": "b",
                "input": "The parcel arrived late — anything you can do?",
                "expected": "Offer tracking help.",
                "tags": {"domain": "support", "action": "execution", "behavior": ["amount_below_limit"]},
                "metadata": {"stale": True, "created_at": "2024-03-01"},
            },
        ],
    }
    data.update(kwargs)
    return parse_suite(data)


def test_parcel_paraphrase_is_merge():
    result = analyze_suite(_tiny_suite())
    pair = next(p for p in result.pairs if {p.left_id, p.right_id} == {"a", "b"})
    assert pair.recommendation == RecommendationState.MERGE
    assert pair.semantic >= 0.80
    assert pair.behavior_overlap >= 0.99


def test_hard_negative_vocabulary_overlap_not_merged():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "plain",
                    "input": "Refund $600 for order 9",
                    "expected": "Escalate above limit",
                    "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
                },
                {
                    "id": "credit",
                    "input": "Refund $600 for order 9 after store credit",
                    "expected": "Do not double-pay",
                    "tags": {
                        "domain": "refund",
                        "action": "clarification",
                        "behavior": ["store_credit_already_issued"],
                    },
                },
            ]
        }
    )
    result = analyze_suite(suite)
    states = {r.state for r in result.recommendations}
    assert RecommendationState.MERGE not in states
    assert RecommendationState.RETIRE not in states


def test_false_retirement_unique_critical():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "dup1",
                    "input": "hello there",
                    "expected": "hi",
                    "tags": {"domain": "support", "action": "apology"},
                },
                {
                    "id": "dup2",
                    "input": "hello there",
                    "expected": "hi",
                    "tags": {"domain": "support", "action": "apology"},
                },
                {
                    "id": "only",
                    "input": "delete my account",
                    "expected": "auth",
                    "tags": {"domain": "privacy", "behavior": ["destructive"], "critical": True},
                },
            ],
        }
    )
    rec = next(r for r in analyze_suite(suite).recommendations if r.test_id == "only")
    assert rec.state == RecommendationState.KEEP
    expl = explain_test(suite, "only")
    assert expl["verdict"] == "KEEP"


def test_status_json_schema():
    payload = project_status(load_suite(DEMO))
    for key in (
        "project",
        "suite_size",
        "active_tests",
        "flaky",
        "stale",
        "conflicts",
        "critical_coverage",
        "evaluation_debt",
        "suite_health",
        "recent_regressions",
        "recommendations",
    ):
        assert key in payload


def test_cli_status_explain_gate_doctor_json():
    st = runner.invoke(app, ["status", str(DEMO), "--format", "json"])
    assert st.exit_code == 0
    json.loads(st.stdout)
    ex = runner.invoke(app, ["explain", "privacy-delete", "--suite", str(DEMO), "--format", "json"])
    assert ex.exit_code == 0
    body = json.loads(ex.stdout)
    assert body["verdict"] == "KEEP"
    gt = runner.invoke(app, ["gate", str(DEMO), "--changed", "refund.py", "--format", "json"])
    assert gt.exit_code == 0
    json.loads(gt.stdout)
    doc = runner.invoke(app, ["doctor", "--format", "json"])
    assert doc.exit_code == 0
    d = json.loads(doc.stdout)
    assert d["overall"] in {"PASS", "WARN", "FAIL"}


def test_cli_json_commands_parse():
    for args in (
        ["analyze", str(DEMO), "--format", "json"],
        ["health", str(DEMO), "--format", "json"],
        ["debt", str(DEMO), "--format", "json"],
        ["flaky", str(DEMO), "--format", "json"],
        ["benchmark", "benchmarks/coding_agent/suite.yaml", "--format", "json"],
        ["impacted-tests", str(DEMO), "examples/demo_suite.yaml", "--format", "json"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.stdout
        json.loads(result.stdout)


def test_impacted_priorities_and_evidence():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "direct",
                    "input": "x",
                    "expected": "y",
                    "provenance_files": ["src/refund.py"],
                    "tags": {"critical": True, "domain": "refund"},
                },
                {
                    "id": "adj",
                    "input": "x",
                    "expected": "y",
                    "tags": {"domain": "refund"},
                    "failure_family": "pay",
                },
                {
                    "id": "risky",
                    "input": "x",
                    "expected": "y",
                    "tags": {"domain": "refund"},
                    "quarantined": True,
                    "failure_family": "pay",
                },
                {"id": "other", "input": "z", "expected": "q", "tags": {"domain": "privacy"}},
            ]
        }
    )
    rows = impacted_tests(suite, ["src/refund.py"])
    by = {r["test_id"]: r for r in rows}
    assert by["direct"]["priority"] == "CRITICAL"
    assert "provenance_file" in by["direct"]["evidence"]
    assert by["risky"]["priority"] in {"RISKY", "CRITICAL", "ADJACENT"}


def test_gate_selects_without_running_agent():
    payload = gate(load_suite(DEMO), changed_paths=["privacy.py"], fast=True)
    assert "selected_tests" in payload


def test_doctor_environment():
    payload = doctor()
    assert payload["network"]["default"] == "no network"


def test_cache_hit_miss_and_algo_invalidation(isolated_store, monkeypatch):
    suite = load_suite(DEMO)
    first = analyze_suite(suite, use_cache=True)
    assert first.timings.get("cache_hit") != 1.0
    second = analyze_suite(suite, use_cache=True)
    assert second.timings.get("cache_hit") == 1.0
    mutated = suite.model_copy(deep=True)
    mutated.tests[0] = mutated.tests[0].model_copy(update={"input": mutated.tests[0].input + " extra"})
    third = analyze_suite(mutated, use_cache=True)
    assert third.timings.get("cache_hit") != 1.0
    fp = suite_fingerprint(suite)
    store_cached_analysis(suite, first)
    assert load_cached_analysis(suite) is not None
    monkeypatch.setattr("evaltrim.cache.ANALYSIS_ALGO_VERSION", ANALYSIS_ALGO_VERSION + "-x")
    from evaltrim.cache import suite_fingerprint as fp2

    assert fp2(suite) != fp


def test_pair_cache_hit_on_unchanged_suite(isolated_store):
    suite = _tiny_suite().model_copy(update={"name": "inc-demo"})
    analyze_suite(suite, use_cache=False)
    cache = PairScoreCache.load(suite)
    assert cache is not None
    left, right = suite.tests
    # First analyze stored pairs; load again after second pass.
    analyze_suite(suite, use_cache=False)
    cache2 = PairScoreCache.load(suite)
    hit = cache2.get(left, right) if cache2 else None
    assert hit is not None
    changed = left.model_copy(update={"input": left.input + " now"})
    assert content_hash_for_test(changed) != content_hash_for_test(left)


def test_malformed_policy_and_thresholds():
    with pytest.raises(ValidationError):
        SafetyPolicies(minimum_retirement_confidence=0.1)
    with pytest.raises(ValidationError):
        AnalysisConfig(merge_threshold=0.5, redundancy_threshold=0.9)
    with pytest.raises(SuiteValidationError):
        parse_suite({"config": {"redundancy_threshold": 1.5}, "tests": [{"id": "a", "input": "i", "expected": "e"}]})


def test_empty_duplicate_bad_yaml_json(tmp_path):
    missing = runner.invoke(app, ["validate", str(tmp_path / "nope.yaml")])
    assert missing.exit_code == 2
    bad = tmp_path / "bad.yaml"
    bad.write_text("tests: [", encoding="utf-8")
    assert runner.invoke(app, ["validate", str(bad)]).exit_code == 2
    js = tmp_path / "bad.json"
    js.write_text("{", encoding="utf-8")
    assert runner.invoke(app, ["validate", str(js)]).exit_code == 2
    empty = tmp_path / "empty.yaml"
    empty.write_text("tests: []\n", encoding="utf-8")
    assert runner.invoke(app, ["validate", str(empty)]).exit_code == 2
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "tests:\n  - id: a\n    input: i\n    expected: e\n  - id: a\n    input: j\n    expected: f\n",
        encoding="utf-8",
    )
    assert runner.invoke(app, ["validate", str(dup)]).exit_code == 2


def test_bad_policy_yaml(tmp_path):
    path = tmp_path / "evaltrim.yaml"
    path.write_text("policies: [\n", encoding="utf-8")
    with pytest.raises(PolicyError):
        load_policy_file(path)


def test_corrupt_trace(tmp_path):
    path = tmp_path / "t.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SuiteValidationError):
        load_traces(path)


def test_corrupt_cache_is_miss(isolated_store):
    suite = load_suite(DEMO)
    key = "analysis:" + suite_fingerprint(suite)
    put_kv("analysis", key, {"not": "an analysis"})
    assert load_cached_analysis(suite) is None


def test_experiments_cache_and_determinism(isolated_store):
    baseline = [{"id": "t1", "passed": True, "latency_ms": 10, "cost_usd": 0.1, "tool_calls": ["a"]}]
    current = [{"id": "t1", "passed": False, "latency_ms": 12, "cost_usd": 0.2, "tool_calls": ["b"]}]
    a = compare_experiments(baseline, current)
    b = compare_experiments(baseline, current)
    assert a["quality"] == b["quality"]
    assert b["cache"] == "hit"
    assert a["tool_behavior"]["changed"] == 1


def test_mcp_dispatch_limited():
    assert "get_status" in TOOLS
    payload = dispatch("get_status", {"suite": str(DEMO)})
    assert "suite_size" in payload
    unknown = dispatch("launch_rockets", {"suite": str(DEMO)})
    assert "error" in unknown


def test_watch_debounce_no_duplicate():
    _events, fire = debounce(["a"], window_s=1.0, last_fire=10.0, now=10.2)
    assert fire is False
    _events, fire = debounce(["a"], window_s=0.1, last_fire=0.0, now=1.0)
    assert fire is True
    prev = watch_once(Path("examples"))
    again = watch_once(Path("examples"), prev)
    assert isinstance(again, dict)


def test_windows_style_impacted_path():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "w",
                    "input": "x",
                    "expected": "y",
                    "provenance_files": [r"src\\refund.py"],
                }
            ]
        }
    )
    rows = impacted_tests(suite, ["src/refund.py"])
    assert rows[0]["priority"] in {"DIRECT", "CRITICAL"}


def test_determinism_recommendations():
    suite = load_suite(DEMO)
    a = analyze_suite(suite, use_cache=False)
    b = analyze_suite(suite, use_cache=False)
    recs_a = [r.model_dump(mode="json") for r in a.recommendations]
    recs_b = [r.model_dump(mode="json") for r in b.recommendations]
    assert recs_a == recs_b


def test_expanded_paraphrase_and_negatives():
    paraphrases = [
        ("Please refund $40", "I need a return of 40 dollars"),
        ("Cancel my order now", "order cancel now"),
        ("The tracking number is missing", "tracking number missing"),
        ("Ship to the office, then email me", "Email me after you ship to the office"),
    ]
    for left, right in paraphrases:
        suite = parse_suite(
            {
                "tests": [
                    {
                        "id": "l",
                        "input": left,
                        "expected": "ok",
                        "tags": {"domain": "support", "action": "execution", "behavior": ["amount_below_limit"]},
                    },
                    {
                        "id": "r",
                        "input": right,
                        "expected": "ok",
                        "tags": {"domain": "support", "action": "execution", "behavior": ["amount_below_limit"]},
                    },
                ]
            }
        )
        result = analyze_suite(suite)
        assert result.pairs[0].semantic >= 0.75


def test_evidence_ledger_fields():
    rec = next(r for r in analyze_suite(load_suite(DEMO)).recommendations)
    assert rec.evidence is not None
    dump = rec.evidence.model_dump(mode="json")
    for key in (
        "semantic_similarity",
        "behavior_overlap",
        "unique_witnesses_lost",
        "critical_coverage_lost",
        "requirement_coverage_lost",
        "historical_failure_contribution",
        "counterfactual_status",
    ):
        assert key in dump


def test_portfolio_constraints():
    suite = load_suite(DEMO)
    result = analyze_suite(suite)
    port = select_portfolio(suite, result, max_tests=2)
    assert "evidence" in port
    assert port["selected"]
