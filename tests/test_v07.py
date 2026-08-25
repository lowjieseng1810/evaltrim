from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult, GraderSpec, Usage
from evaltrim.evaluation.graders import REGISTRY, Grader, grade_record, register_grader
from evaltrim.evaluation.statistics import compare_samples, percentile, summarize_runs, welch_ttest
from evaltrim.experiments import experiment_matrix
from evaltrim.flake import classify_flake
from evaltrim.ingest import compress_production_failures
from evaltrim.intelligence.mutation import mutation_score
from evaltrim.models import FlakeStatus, RunStats, Tags, TestCase
from evaltrim.parser import parse_suite
from evaltrim.regression.runs import classify_run_delta, compare_runs
from evaltrim.sandbox import LocalSandbox
from evaltrim.scenarios import Scenario, ScenarioTurn, replay_scenario
from evaltrim.security import evaluate_security


def test_plugin_graders():
    rec = EvaluationRecord(id="t", input="hi", expected="hello world")
    out = AgentOutput(text="hello world", usage=Usage(latency_ms=5, ttft_ms=1, total_tokens=9, cost_usd=0.0))
    rec.graders = [
        GraderSpec(type="exact", params={"expected": "hello world"}),
        GraderSpec(type="contains"),
        GraderSpec(type="not_contains", params={"text": "secret"}),
        GraderSpec(type="regex", params={"pattern": "hello"}),
        GraderSpec(type="json", params={"schema": {"type": "object", "required": ["a"]}}),
        GraderSpec(type="latency", params={"max_ms": 100}),
        GraderSpec(type="ttft", params={"max_ms": 10}),
        GraderSpec(type="tokens", params={"max_tokens": 100}),
        GraderSpec(type="cost", params={"max_usd": 1}),
    ]
    json_out = AgentOutput(text='{"a": 1}', usage=out.usage)
    schema = GraderSpec(type="json", params={"schema": {"type": "object", "required": ["a"]}})
    grades = grade_record(rec.model_copy(update={"graders": [schema]}), json_out)
    assert grades[0].passed is True
    exact = grade_record(rec.model_copy(update={"graders": [GraderSpec(type="exact")]}), out)
    assert exact[0].passed is True
    assert "tool_args" in REGISTRY
    assert "ttft" in REGISTRY


def test_register_grader_plugin():
    class AlwaysPass(Grader):
        name = "always_pass"

        def grade(self, record, output, spec):
            return GradeResult(grader=self.name, passed=True, score=1.0, detail="plugin")

    register_grader(AlwaysPass)
    rec = EvaluationRecord(id="t", input="x", expected="y", graders=[GraderSpec(type="always_pass")])
    assert grade_record(rec, AgentOutput(text="y"))[0].passed is True


def test_tool_args_and_trajectory_lcs():
    from evaltrim.core.manifest import ToolCallRecord, TrajectoryStep

    rec = EvaluationRecord(
        id="t",
        input="x",
        expected="y",
        graders=[
            GraderSpec(
                type="tool_args",
                params={"constraints": [{"name": "refund", "required_args": ["amount"], "equals": {"amount": 20}}]},
            ),
            GraderSpec(type="trajectory", params={"mode": "lcs", "order": ["a", "b"], "threshold": 1.0}),
        ],
    )
    out = AgentOutput(
        text="y",
        tool_calls=[ToolCallRecord(name="refund", arguments={"amount": 20})],
        trajectory=[TrajectoryStep(kind="a"), TrajectoryStep(kind="b")],
    )
    grades = grade_record(rec, out)
    assert all(g.passed for g in grades)


def test_stats_false_regression_and_percentiles():
    same = [2.0] * 12
    cmp = compare_samples(same, list(same))
    assert cmp["statistically_significant"] is False
    assert cmp["regression_flag"] is False
    shifted = [8.0] * 12
    cmp2 = compare_samples(same, shifted)
    assert cmp2["statistically_significant"] is True
    welch = welch_ttest(same, shifted)
    assert welch["p_two_sided"] is not None
    assert percentile([1, 2, 3, 4], 50) == 2.5
    summary = summarize_runs([True, True, False], [10.0, 20.0, 30.0])
    assert summary["latency_p90"] is not None
    assert summary["latency_stdev"] is not None


def test_unchanged_and_provider_error():
    a = {"id": "t", "output": "ok", "passed": True, "tool_calls": [], "latency_ms": 1}
    assert compare_runs([a], [a])["counts"]["UNCHANGED"] == 1
    delta = classify_run_delta(a, {**a, "passed": False, "output": "boom", "error_kind": "timeout"})
    assert delta["class"] != "CONFIRMED_REGRESSION"
    assert delta["likely_source"] == "ENVIRONMENT"


def test_environmental_flake():
    test = TestCase(
        id="e",
        input="x",
        expected="y",
        tags=Tags(),
        run_stats=RunStats(runs=4, passes=1, failures=3, outcomes=["pass", "timeout", "provider_error", "timeout"]),
    )
    status, detail = classify_flake(test)
    assert status == FlakeStatus.ENVIRONMENTAL
    assert detail["failure_kind"] == "infrastructure"


def test_experiment_pareto():
    payload = experiment_matrix(
        [
            {
                "id": "cheap",
                "dimensions": {"model": "a"},
                "cases": [{"passed": True, "cost_usd": 0.01, "latency_ms": 40}],
            },
            {
                "id": "fast",
                "dimensions": {"model": "b"},
                "cases": [{"passed": True, "cost_usd": 0.2, "latency_ms": 5}],
            },
            {
                "id": "quality",
                "dimensions": {"model": "c"},
                "cases": [{"passed": True, "cost_usd": 1.0, "latency_ms": 80}],
            },
            {
                "id": "worse",
                "dimensions": {"model": "d"},
                "cases": [{"passed": False, "cost_usd": 2.0, "latency_ms": 90}],
            },
        ]
    )
    assert payload["BEST_QUALITY"]["id"] in {"cheap", "fast", "quality"}
    assert payload["BEST_COST"]["id"] == "cheap"
    assert payload["BEST_LATENCY"]["id"] == "fast"
    assert payload["BEST_PARETO_OPTION"]["id"] in {row["id"] for row in payload["pareto_frontier"]}


def test_mutation_and_security_and_sandbox(tmp_path):
    mut = mutation_score()
    assert mut["mutation_score"] >= 0.5
    sec = evaluate_security()
    assert sec["detection_rate"] == 1.0
    assert sec["false_positives"] == 0
    box = LocalSandbox(root=tmp_path, tool_mocks={"add": lambda x, y: x + y})
    box.write_text("a.txt", "hi")
    assert box.read_text("a.txt") == "hi"
    assert box.call_tool("add", x=1, y=2) == 3
    ran = box.run(["python3", "-c", "print(2)"])
    assert ran["returncode"] == 0


def test_scenario_replay():
    scene = Scenario(
        id="s",
        persona="persistent",
        style="adversarial",
        turns=[ScenarioTurn(user="refund", expected="refund")],
    )
    payload = replay_scenario(scene)
    assert payload["reproducibility"] == 1.0
    assert payload["turns"][0]["passed"] is True


def test_failure_compression():
    records = [{"id": f"f{i}", "input": "same boom", "failure_family": "timeout"} for i in range(20)]
    records += [{"id": "new", "input": "other", "failure_family": "schema"}]
    out = compress_production_failures(records)
    assert out["failure_families"] == 2
    assert out["production_failures"] == 21
    assert out["compression_ratio"] < 1.0


def test_analyze_attaches_intelligence():
    from evaltrim.analyze import analyze_suite

    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "refund 600",
                    "expected": "escalate",
                    "tags": {"domain": "refund", "behavior": ["destructive"], "critical": True},
                },
                {"id": "b", "input": "hello", "expected": "hi", "tags": {"domain": "chitchat"}},
            ]
        }
    )
    result = analyze_suite(suite)
    assert result.contract_version == "1.0"
    assert result.clusters
    assert result.information_gain
    assert result.recommendations[0].evidence
    assert result.recommendations[0].evidence.proof
