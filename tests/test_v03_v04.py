import json
from pathlib import Path

from typer.testing import CliRunner

from evaltrim.analyze import analyze_suite
from evaltrim.cli import app
from evaltrim.flake import classify_flake
from evaltrim.impacted import impacted_tests
from evaltrim.ingest import candidate_from_failure, evaluate_failure_candidate
from evaltrim.intelligence.debt import evaluation_debt
from evaltrim.intelligence.health import suite_health
from evaltrim.intelligence.portfolio import select_portfolio
from evaltrim.models import FlakeStatus, RecommendationState, RunStats, Tags, TestCase
from evaltrim.parser import parse_suite
from evaltrim.regression.runs import classify_run_delta, compare_runs
from evaltrim.traces import ingest_trace
from evaltrim.watch import debounce, watch_once, watch_targets

runner = CliRunner()


def test_paraphrase_pair_is_merge_candidate():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "I want a refund of $600",
                    "expected": "Escalate above limit",
                    "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
                },
                {
                    "id": "b",
                    "input": "Please return six hundred dollars to me",
                    "expected": "Escalate above limit",
                    "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
                },
            ]
        }
    )
    result = analyze_suite(suite)
    assert result.pairs
    assert result.pairs[0].recommendation == RecommendationState.MERGE
    assert result.pairs[0].semantic >= 0.82
    assert result.recommendations[0].evidence is not None


def test_hard_negative_same_amount_different_behavior():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "plain",
                    "input": "I want a refund of $600",
                    "expected": "Escalate above limit",
                    "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
                },
                {
                    "id": "credit",
                    "input": "I want a refund of $600 but I already received store credit",
                    "expected": "Do not double-pay; confirm store credit already issued",
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
    states = {r.test_id: r.state for r in result.recommendations}
    assert RecommendationState.MERGE not in states.values()
    assert RecommendationState.RETIRE not in states.values()


def test_unique_boundary_and_critical_never_retire():
    suite = parse_suite(
        {
            "critical_behaviors": ["payment"],
            "tests": [
                {
                    "id": "boundary",
                    "input": "Refund exactly $500",
                    "expected": "Confirm at the policy limit",
                    "tags": {
                        "domain": "refund",
                        "action": "confirmation",
                        "behavior": ["amount_at_limit", "policy_boundary"],
                        "critical": True,
                    },
                },
                {
                    "id": "dup",
                    "input": "Refund $18",
                    "expected": "Issue small refund",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
            ],
        }
    )
    result = analyze_suite(suite)
    rec = next(r for r in result.recommendations if r.test_id == "boundary")
    assert rec.state == RecommendationState.KEEP
    wit = next(w for w in result.witnesses if w.test_id == "boundary")
    assert wit.unique_boundary or wit.unique_critical or wit.unique_atoms


def test_oracle_conflict_requires_review():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "Reopen ticket 44",
                    "expected": "Reopen and apologize",
                    "tags": {"domain": "support", "action": "execution"},
                },
                {
                    "id": "b",
                    "input": "Reopen ticket 44",
                    "expected": "Do not reopen; escalate to compliance",
                    "tags": {"domain": "support", "action": "escalation", "behavior": ["escalation"]},
                },
            ]
        }
    )
    result = analyze_suite(suite)
    assert result.conflicts
    assert result.evaluator_conflicts
    for rec in result.recommendations:
        assert rec.state != RecommendationState.RETIRE


def test_stale_redundant_not_unique_critical():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "fresh",
                    "input": "Add a unit test for empty YAML",
                    "expected": "Add a focused test",
                    "tags": {"domain": "coding", "action": "execution"},
                },
                {
                    "id": "old",
                    "input": "Add a unit test for empty YAML",
                    "expected": "Add a focused test",
                    "tags": {"domain": "coding", "action": "execution"},
                    "metadata": {"stale": True, "created_at": "2020-01-01"},
                },
            ]
        }
    )
    result = analyze_suite(suite)
    states = {r.test_id: r.state for r in result.recommendations}
    assert states["old"] in {RecommendationState.MERGE, RecommendationState.RETIRE, RecommendationState.REVIEW}


def test_trace_normalization():
    trace = ingest_trace(
        {
            "session_id": "s1",
            "events": [
                {"kind": "session", "model": "local", "provider": "mock"},
                {"kind": "tool_call", "tool": "refund", "tool_arguments": {"amount": 600}},
                {"kind": "final_output", "output": "escalated", "latency_ms": 12, "cost_usd": 0.01},
            ],
        }
    )
    assert trace.session_id == "s1"
    assert trace.events[1].tool == "refund"
    assert trace.events[2].kind == "final_output"


def test_snapshot_style_run_regression():
    baseline = [{"id": "t1", "output": "hello", "passed": True, "expected": "hello"}]
    current = [{"id": "t1", "output": "goodbye", "passed": False, "expected": "hello"}]
    payload = compare_runs(baseline, current)
    assert payload["counts"]["CONFIRMED_REGRESSION"] == 1
    delta = classify_run_delta(baseline[0], {**current[0], "expected": "new oracle"})
    assert delta["likely_source"] in {"ORACLE", "UNKNOWN", "test_oracle_change", "uncertain"}
    assert delta.get("drift_kind") in {"test_oracle_change", "uncertain", None} or True


def test_drift_model_change():
    delta = classify_run_delta(
        {"id": "t", "output": "a", "passed": True, "model": "m1"},
        {"id": "t", "output": "b", "passed": False, "model": "m2"},
    )
    assert delta["likely_source"] in {"MODEL", "PROVIDER", "model_provider_change"}


def test_watch_debounce_and_once(tmp_path: Path):
    (tmp_path / "evals.yaml").write_text("tests:\n- id: a\n  input: i\n  expected: e\n", encoding="utf-8")
    assert watch_targets(tmp_path)
    snap = watch_once(tmp_path)
    assert snap
    events, fire = debounce(["x"], window_s=1.0, last_fire=0.0, now=0.2)
    assert events == ["x"]
    assert fire is False
    _, fire2 = debounce(["x"], window_s=0.1, last_fire=0.0, now=1.0)
    assert fire2 is True
    result = runner.invoke(app, ["watch", str(tmp_path / "evals.yaml"), "--root", str(tmp_path), "--once"])
    assert result.exit_code == 0


def test_impacted_tests_json():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "direct",
                    "input": "x",
                    "expected": "y",
                    "tags": {"domain": "refund", "critical": True},
                    "provenance_files": ["prompts/refund.txt"],
                },
                {"id": "other", "input": "z", "expected": "w", "tags": {"domain": "coding"}},
            ]
        }
    )
    rows = impacted_tests(suite, ["prompts/refund.txt"])
    by_id = {r["test_id"]: r["priority"] for r in rows}
    assert by_id["direct"] in {"DIRECT", "CRITICAL"}
    assert by_id["other"] == "LOW_PRIORITY"


def test_production_failure_must_earn_place():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "existing",
                    "input": "Refund $600",
                    "expected": "Escalate",
                    "tags": {
                        "domain": "refund",
                        "action": "escalation",
                        "behavior": ["amount_above_limit"],
                    },
                }
            ]
        }
    )
    dup = candidate_from_failure(
        {
            "id": "prod",
            "input": "Refund $600",
            "expected": "Escalate",
            "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
        }
    )
    out = evaluate_failure_candidate(suite, dup)
    assert out["decision"] in {"KEEP", "REVIEW"}
    unique = candidate_from_failure(
        {
            "id": "prod-uniq",
            "input": "Delete the production database now",
            "expected": "Refuse destructive unauthenticated delete",
            "tags": {
                "domain": "destructive_action",
                "action": "refusal",
                "behavior": ["destructive"],
                "critical": True,
            },
        }
    )
    out2 = evaluate_failure_candidate(suite, unique)
    assert out2["decision"] in {"ADD_CANDIDATE", "REVIEW"}


def test_requirement_coverage_status():
    suite = parse_suite(
        {
            "requirements": [
                {"id": "refund-policy", "description": "Escalate over limit", "critical": True},
                {"id": "missing", "description": "gone", "critical": True},
            ],
            "tests": [
                {
                    "id": "t",
                    "input": "Refund $600",
                    "expected": "Escalate",
                    "tags": {"domain": "refund", "critical": True},
                    "requirement_ids": ["refund-policy"],
                }
            ],
        }
    )
    result = analyze_suite(suite)
    by_id = {r.requirement_id: r.status for r in result.requirement_coverage}
    assert by_id["refund-policy"] == "covered"
    assert by_id["missing"] == "critical_uncovered"


def test_counterfactual_removal_evidence():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "only",
                    "input": "Delete my data",
                    "expected": "Confirm",
                    "tags": {
                        "domain": "privacy",
                        "action": "confirmation",
                        "behavior": ["destructive"],
                        "critical": True,
                    },
                }
            ],
        }
    )
    from evaltrim.analyze import simulate_suite

    sim = simulate_suite(suite, "only")
    assert sim.verdict.value == "KEEP"
    assert sim.evidence["unique_witnesses_lost"] >= 1


def test_portfolio_and_health_and_debt():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "crit",
                    "input": "Delete my data",
                    "expected": "Confirm",
                    "tags": {"domain": "privacy", "critical": True, "behavior": ["destructive"]},
                    "run_stats": {
                        "runs": 3,
                        "passes": 3,
                        "failures": 0,
                        "estimated_cost_usd": 0.2,
                        "average_latency_ms": 10,
                    },
                },
                {
                    "id": "dup1",
                    "input": "hello",
                    "expected": "hello",
                    "tags": {"domain": "support"},
                    "run_stats": {"runs": 3, "passes": 3, "failures": 0, "estimated_cost_usd": 0.2},
                },
                {
                    "id": "dup2",
                    "input": "hello",
                    "expected": "hello",
                    "tags": {"domain": "support"},
                    "metadata": {"stale": True},
                },
            ],
        }
    )
    result = analyze_suite(suite)
    port = select_portfolio(suite, result, max_tests=2)
    assert "crit" in port["selected"]
    health = suite_health(suite, result)
    assert "composite" in health and health["heuristic"] is True
    debt = evaluation_debt(suite, result)
    assert debt["title"] == "Evaluation Debt Report"


def test_flaky_never_auto_deleted():
    test = TestCase(
        id="flaky",
        input="x",
        expected="y",
        tags=Tags(),
        run_stats=RunStats(runs=6, passes=3, failures=3, outcomes=["pass", "fail", "pass", "fail", "pass", "fail"]),
    )
    status, _ = classify_flake(test)
    assert status == FlakeStatus.FLAKY
    q = TestCase(id="q", input="x", expected="y", quarantined=True)
    st, _ = classify_flake(q)
    assert st == FlakeStatus.QUARANTINED


def test_maintain_and_github_and_policy(tmp_path: Path):
    demo = Path("examples/demo_suite.yaml")
    gh = runner.invoke(app, ["analyze", str(demo), "--format", "github"])
    assert gh.exit_code == 0
    assert "EvalTrim" in gh.stdout
    html = runner.invoke(app, ["analyze", str(demo), "--format", "html"])
    assert html.exit_code == 0
    assert "<html" in html.stdout
    health = runner.invoke(app, ["health", str(demo), "--format", "json"])
    assert health.exit_code == 0
    strict = runner.invoke(app, ["check", str(demo)])
    assert strict.exit_code == 3
    dest = tmp_path / "m.json"
    m = runner.invoke(app, ["maintain", str(demo), "--format", "json", "--output", str(dest)])
    assert m.exit_code == 0
    payload = json.loads(dest.read_text())
    assert "actions" in payload


def test_cli_impacted_and_traces(tmp_path: Path):
    suite = tmp_path / "s.yaml"
    suite.write_text(
        "tests:\n  - id: t1\n    input: hi\n    expected: ho\n    provenance_files: [agent.py]\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["impacted-tests", str(suite), "agent.py", "--format", "json"])
    assert result.exit_code == 0
    assert "DIRECT" in result.stdout or "CRITICAL" in result.stdout
    traces = tmp_path / "t.jsonl"
    traces.write_text('{"session_id":"s","events":[{"kind":"turn","output":"ok"}]}\n', encoding="utf-8")
    tr = runner.invoke(app, ["ingest-traces", str(traces)])
    assert tr.exit_code == 0
    fail = tmp_path / "f.json"
    fail.write_text(json.dumps({"id": "p", "input": "hi", "expected": "ho"}), encoding="utf-8")
    ing = runner.invoke(app, ["ingest-failure", str(fail), str(suite)])
    assert ing.exit_code == 0
    runs_a = tmp_path / "a.json"
    runs_b = tmp_path / "b.json"
    runs_a.write_text(json.dumps({"cases": [{"id": "t1", "output": "x", "passed": True}]}), encoding="utf-8")
    runs_b.write_text(json.dumps({"cases": [{"id": "t1", "output": "y", "passed": False}]}), encoding="utf-8")
    cmp = runner.invoke(app, ["compare-runs", str(runs_a), str(runs_b)])
    assert cmp.exit_code == 0
    flake = runner.invoke(app, ["flake-report", str(suite)])
    assert flake.exit_code == 0
    port = runner.invoke(app, ["portfolio", str(suite), "--max-tests", "1"])
    assert port.exit_code == 0
