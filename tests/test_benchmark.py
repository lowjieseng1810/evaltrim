from pathlib import Path

from evaltrim.analyze import analyze_suite
from evaltrim.benchmark import run_all_benchmarks, run_benchmark
from evaltrim.models import RecommendationState


def test_demo_never_retires_privacy_delete():
    from evaltrim.parser import load_suite

    suite = load_suite("examples/demo_suite.yaml")
    result = analyze_suite(suite)
    rec = next(r for r in result.recommendations if r.test_id == "privacy-delete")
    assert rec.state == RecommendationState.KEEP


def test_customer_support_benchmark_safety():
    row = run_benchmark(
        Path("benchmarks/customer_support/suite.yaml"),
        Path("benchmarks/customer_support/benchmark_metadata.yaml"),
    )
    assert row["retirement_safety_rate"] == 1.0
    assert row["deterministic"] is True
    assert row["unsafe_retirements"] == []
    assert row["critical_coverage"] == 1.0


def test_all_benchmarks_preserve_criticals():
    payload = run_all_benchmarks(Path("benchmarks"))
    assert len(payload["benchmarks"]) >= 3
    for row in payload["benchmarks"]:
        assert row["deterministic"] is True
        assert row["retirement_safety_rate"] == 1.0
