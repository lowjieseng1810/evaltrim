from pathlib import Path

from evaltrim.analyze import analyze_suite
from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GraderSpec, Usage
from evaltrim.evaluation.graders import grade_record, overall_pass
from evaltrim.evaluation.statistics import mean, median, pass_rate, variance
from evaltrim.integrations.jsonl import import_jsonl
from evaltrim.models import Behavior, RecommendationState, RedundancyWeights, TestCase
from evaltrim.normalize import normalize_text
from evaltrim.parser import parse_suite
from evaltrim.regression.compare import compare_analysis
from evaltrim.runtime.adapters import EchoExpectedAdapter
from evaltrim.runtime.runner import run_suite
from evaltrim.similarity import SimilarityEngine


def test_paraphrase_refund_is_related():
    tests = [
        TestCase(id="a", input="I want a refund of $600", expected="escalate"),
        TestCase(id="b", input="Please return six hundred dollars to me", expected="escalate"),
    ]
    beh = [
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
    ]
    engine = SimilarityEngine(tests, beh, RedundancyWeights())
    pair = engine.pair_score("a", "b")
    assert float(pair["semantic"]) >= 0.45
    assert normalize_text(tests[0].input).count("refund")
    assert "amt_600" in normalize_text(tests[1].input)


def test_hard_negative_not_collapsed():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "plain",
                    "input": "I want a refund of $600",
                    "expected": "Escalate above limit",
                    "tags": {
                        "domain": "refund",
                        "action": "escalation",
                        "behavior": ["amount_above_limit"],
                    },
                },
                {
                    "id": "credit",
                    "input": "I want a refund of $600 but I have already received store credit",
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
    assert states["plain"] != RecommendationState.RETIRE
    assert states["credit"] != RecommendationState.RETIRE
    assert states["plain"] != RecommendationState.MERGE
    assert states["credit"] != RecommendationState.MERGE


def test_contains_grader_and_echo_runner():
    suite = parse_suite({"tests": [{"id": "t1", "input": "hello", "expected": "hello"}]})
    batch = run_suite(suite, adapter=EchoExpectedAdapter())
    assert batch.cases[0].passed is True
    assert batch.summary["pass_rate"] == 1.0


def test_json_grader():
    rec = EvaluationRecord(
        id="j",
        input="{}",
        expected="",
        graders=[GraderSpec(type="json", params={"required": ["ok"]})],
    )
    grades = grade_record(rec, AgentOutput(text='{"ok": true}'))
    assert overall_pass(grades) is True
    grades2 = grade_record(rec, AgentOutput(text="not-json"))
    assert overall_pass(grades2) is False


def test_latency_grader_skip_without_data():
    rec = EvaluationRecord(id="l", input="x", expected="y", graders=[GraderSpec(type="latency")])
    grades = grade_record(rec, AgentOutput(text="y", usage=Usage()))
    assert grades[0].skipped is True


def test_statistics():
    assert mean([1.0, 3.0]) == 2.0
    assert median([1.0, 2.0, 3.0]) == 2.0
    assert variance([1.0, 1.0, 1.0]) == 0.0
    assert pass_rate([True, False]) == 0.5


def test_jsonl_import(tmp_path: Path):
    path = tmp_path / "rows.jsonl"
    path.write_text(
        '{"id":"a","input":"hi","expected":"there"}\n{"prompt":"second","ideal":"out"}\n',
        encoding="utf-8",
    )
    suite = import_jsonl(path)
    assert len(suite.tests) == 2
    assert suite.tests[0].id == "a"


def test_windows_like_path(tmp_path: Path):
    folder = tmp_path / "suite files"
    folder.mkdir()
    dest = folder / "my suite.yaml"
    dest.write_text("tests:\n  - id: z\n    input: i\n    expected: e\n", encoding="utf-8")
    from evaltrim.parser import load_suite

    assert load_suite(dest).tests[0].id == "z"


def test_embeddings_fallback_none_by_default():
    from evaltrim.embeddings import load_encoder

    assert load_encoder(enabled=False) is None
    enc = load_encoder(enabled=True)
    assert enc is not None
    v = enc.encode("refund 600")
    assert v == enc.encode("refund 600")


def test_compare_two_mini_suites():
    a = parse_suite({"tests": [{"id": "t", "input": "a", "expected": "b"}]})
    b = parse_suite(
        {
            "tests": [
                {"id": "t", "input": "a", "expected": "b"},
                {"id": "u", "input": "c", "expected": "d"},
            ]
        }
    )
    diff = compare_analysis(analyze_suite(a), analyze_suite(b))
    assert diff["tests"]["before"] == 1
    assert diff["tests"]["after"] == 2
    assert "u" in diff["tests"]["added"]
