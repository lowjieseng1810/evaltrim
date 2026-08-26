from pathlib import Path

from typer.testing import CliRunner

from evaltrim.analyze import analyze_suite
from evaltrim.benchmark import run_benchmark
from evaltrim.cli import app
from evaltrim.intelligence.witness import classify_witness, unique_signatures
from evaltrim.models import Behavior, CoverageResult, RecommendationState, RemovalSimulation, Tags, TestCase, Verdict
from evaltrim.parser import load_suite, parse_suite

runner = CliRunner()


def _cov() -> CoverageResult:
    return CoverageResult(
        behavior_atoms=1,
        covered_atoms=1,
        behavior_coverage=1.0,
        critical_atoms=1,
        covered_critical_atoms=1,
        critical_coverage=1.0,
    )


def _sim(**kwargs) -> RemovalSimulation:
    return RemovalSimulation(
        test_id=kwargs.get("test_id", "t"),
        before_tests=2,
        after_tests=1,
        before_coverage=_cov(),
        after_coverage=_cov(),
        verdict=kwargs.get("verdict", Verdict.SAFE_TO_RETIRE),
        lost_atoms=kwargs.get("lost_atoms", []),
        lost_critical_atoms=kwargs.get("lost_critical_atoms", []),
        lost_unique_witnesses=kwargs.get("lost_atoms", []),
        reasons=["fixture"],
        unique_witnesses_before=1,
        unique_witnesses_after=1,
    )


def test_classifier_rejects_weak_leftover_and_same_input_conflict():
    weak = TestCase(
        id="pay-ok",
        input="checkout $42",
        expected="charge",
        tags=Tags(domain="payment", action="execution", behavior=["amount_below_limit"], critical=True),
    )
    beh = Behavior(domain="payment", action="execution", conditions=["amount_below_limit"], critical=True)
    out = classify_witness(
        test=weak,
        behavior=beh,
        unique_atoms=["condition:amount_below_limit"],
        unique_critical=[],
        unique_boundary=False,
        unique_requirement=[],
        unique_failure=False,
        unique_failure_family=False,
        unique_signature=True,
        simulation=_sim(),
    )
    assert out["is_unique_witness"] is False
    assert out["is_critical_witness"] is False

    twin = TestCase(id="c-b", input="same", expected="refuse", tags=Tags(domain="coding", critical=True))
    twin_b = Behavior(domain="coding", action="refusal", conditions=["policy_violation"], critical=True)
    conflicted = classify_witness(
        test=twin,
        behavior=twin_b,
        unique_atoms=["condition:policy_violation"],
        unique_critical=[],
        unique_boundary=False,
        unique_requirement=[],
        unique_failure=False,
        unique_failure_family=False,
        unique_signature=True,
        simulation=_sim(),
        conflict=True,
        exact_input_conflict=True,
    )
    assert conflicted["is_unique_witness"] is False


def test_classifier_keeps_exclusive_critical_signature():
    test = TestCase(
        id="traj",
        input="refund without verify",
        expected="must verify",
        tags=Tags(domain="refund", action="execution", behavior=["destructive"], critical=True),
    )
    beh = Behavior(domain="refund", action="execution", conditions=["destructive"], critical=True)
    out = classify_witness(
        test=test,
        behavior=beh,
        unique_atoms=[],
        unique_critical=[],
        unique_boundary=False,
        unique_requirement=[],
        unique_failure=False,
        unique_failure_family=False,
        unique_signature=True,
        simulation=_sim(verdict=Verdict.SAFE_TO_RETIRE),
        conflict=True,
        exact_input_conflict=False,
    )
    assert out["is_unique_witness"] is True
    assert out["is_critical_witness"] is True


def test_labeled_witness_suite_gates():
    row = run_benchmark(Path("benchmarks/witness/suite.yaml"), Path("benchmarks/witness/benchmark_metadata.yaml"))
    assert row["unique_witness_precision"] is not None
    assert row["unique_witness_recall"] is not None
    assert row["unique_witness_precision"] >= 0.95
    assert row["unique_witness_recall"] >= 0.95
    assert row["critical_witness_recall"] == 1.0
    assert row["critical_witness_precision"] == 1.0
    assert row["false_critical_witness_count"] == 0
    assert row["retirement_safety_rate"] == 1.0
    assert row["critical_coverage"] == 1.0
    assert row["false_witness_rate"] in (0.0, 0)


def test_witness_final_gates_and_rare_token():
    row = run_benchmark(
        Path("benchmarks/witness_final/suite.yaml"),
        Path("benchmarks/witness_final/benchmark_metadata.yaml"),
    )
    assert row["unique_witness_precision"] >= 0.95
    assert row["unique_witness_recall"] >= 0.95
    assert row["critical_witness_recall"] == 1.0
    assert row["critical_witness_precision"] == 1.0
    assert row["false_critical_witness_count"] == 0
    assert row["retirement_safety_rate"] == 1.0
    assert row["critical_coverage"] == 1.0
    assert "f-rare-token" not in row["unique_witness_predicted_ids"]
    assert "f-twin-b" not in row["unique_witness_predicted_ids"]
    assert "f-privacy" in row["unique_witness_predicted_ids"]


def test_constructed_suites_unique_witness_floor():
    for name in ("coding_agent", "customer_support", "shopping_agent", "robustness"):
        row = run_benchmark(Path(f"benchmarks/{name}/suite.yaml"), Path(f"benchmarks/{name}/benchmark_metadata.yaml"))
        assert row["retirement_safety_rate"] == 1.0
        assert row["unique_witness_precision"] is not None
        assert row["unique_witness_recall"] is not None
        assert row["unique_witness_precision"] >= 0.95
        assert row["unique_witness_recall"] >= 0.95
        assert row["critical_witness_recall"] == 1.0
        assert row["false_critical_witness_count"] == 0


def test_hard_negative_stays_keep_not_coverage_witness():
    suite = load_suite("benchmarks/customer_support/suite.yaml")
    result = analyze_suite(suite, use_cache=False)
    rec = next(r for r in result.recommendations if r.test_id == "cs-refund-hardneg")
    wit = next(w for w in result.witnesses if w.test_id == "cs-refund-hardneg")
    assert rec.state == RecommendationState.KEEP
    assert wit.is_unique_witness is False


def test_portfolio_witness_objective():
    result = runner.invoke(
        app, ["portfolio", "benchmarks/witness/suite.yaml", "--objective", "witness", "--format", "json"]
    )
    assert result.exit_code == 0
    import json

    payload = json.loads(result.stdout)
    assert payload["objective"] == "witness"
    selected = payload["BEST_WITNESS_PORTFOLIO"]["minimum_practical_witness_set"]
    assert "wit-traj-skip" in selected
    assert "wit-weak-band" not in selected


def test_unique_signatures_are_exclusive():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "x",
                    "expected": "y",
                    "tags": {
                        "domain": "refund",
                        "action": "execution",
                        "behavior": ["destructive"],
                    },
                },
                {
                    "id": "b",
                    "input": "z",
                    "expected": "w",
                    "tags": {
                        "domain": "security",
                        "action": "refusal",
                        "behavior": ["destructive"],
                    },
                },
            ]
        }
    )
    behaviors = [
        Behavior(domain="refund", action="execution", conditions=["destructive"]),
        Behavior(domain="security", action="refusal", conditions=["destructive"]),
    ]
    sigs = unique_signatures(suite.tests, behaviors)
    assert "a" in sigs and "b" in sigs
