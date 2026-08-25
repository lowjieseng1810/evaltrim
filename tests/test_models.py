import pytest
from pydantic import ValidationError

from evaltrim.errors import SuiteValidationError
from evaltrim.models import AnalysisConfig, RedundancyWeights, RunStats, TestCase
from evaltrim.parser import parse_suite


def test_duplicate_ids_rejected():
    with pytest.raises(SuiteValidationError, match="duplicate test id"):
        parse_suite(
            {
                "tests": [
                    {"id": "a", "input": "x", "expected": "y"},
                    {"id": "a", "input": "x2", "expected": "y2"},
                ]
            }
        )


def test_empty_suite_rejected():
    with pytest.raises(SuiteValidationError):
        parse_suite({"tests": []})


def test_run_stats_failure_rate():
    stats = RunStats(runs=10, passes=7, failures=3)
    assert stats.failure_rate == 0.3


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        RedundancyWeights(semantic=0.5, behavior=0.5, expected=0.5, historical=0.5)


def test_test_case_stale_flag():
    t = TestCase(id="s", input="i", expected="e", metadata={"stale": True})
    assert t.is_stale()


def test_config_defaults():
    cfg = AnalysisConfig()
    assert abs(cfg.weights.semantic + cfg.weights.behavior + cfg.weights.expected + cfg.weights.historical - 1) < 1e-9


def test_suite_get():
    suite = parse_suite({"tests": [{"id": "t1", "input": "a", "expected": "b"}]})
    assert suite.get("t1").id == "t1"
    with pytest.raises(KeyError):
        suite.get("missing")
