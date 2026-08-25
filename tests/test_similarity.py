import pytest

from evaltrim.models import Behavior, RedundancyWeights, TestCase
from evaltrim.similarity import SimilarityEngine, jaccard, tokenize


def test_tokenize_and_jaccard():
    assert tokenize("Refund $600") == ["refund", "$600"]
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert jaccard([], []) == 1.0


def test_identical_inputs_score_high():
    tests = [
        TestCase(id="a", input="refund 600 now", expected="escalate"),
        TestCase(id="b", input="refund 600 now", expected="escalate"),
    ]
    behaviors = [
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
    ]
    engine = SimilarityEngine(tests, behaviors, RedundancyWeights())
    pair = engine.pair_score("a", "b")
    assert float(pair["score"]) >= 0.9
    assert pair["shared"]


def test_different_behavior_keeps_unique_atoms():
    tests = [
        TestCase(id="a", input="refund 600 please", expected="escalate above limit"),
        TestCase(id="b", input="refund 600 please", expected="clarify ambiguous intent"),
    ]
    behaviors = [
        Behavior(domain="refund", action="escalation", conditions=["amount_above_limit"]),
        Behavior(domain="refund", action="clarification", conditions=["ambiguous_request"]),
    ]
    engine = SimilarityEngine(tests, behaviors, RedundancyWeights())
    pair = engine.pair_score("a", "b")
    assert pair["unique_left"]
    assert pair["unique_right"]
    # High wording overlap is not enough to erase unique behaviors.
    assert "condition:ambiguous_request" in pair["unique_right"]
