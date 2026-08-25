from evaltrim.analyze import analyze_suite
from evaltrim.models import RecommendationState, TestSuite
from evaltrim.parser import parse_suite


def _suite(tests: list[dict]) -> TestSuite:
    return parse_suite({"critical_behaviors": ["privacy", "payment"], "tests": tests})


def test_redundancy_pair_detected():
    suite = _suite(
        [
            {
                "id": "a",
                "input": "I want a refund of $600",
                "expected": "Escalate above limit",
                "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
            },
            {
                "id": "b",
                "input": "I want a refund of $600",
                "expected": "Escalate above limit",
                "tags": {"domain": "refund", "action": "escalation", "behavior": ["amount_above_limit"]},
            },
        ]
    )
    result = analyze_suite(suite)
    assert result.pairs
    assert result.pairs[0].score >= 0.8


def test_similar_wording_different_behavior_not_merged():
    suite = _suite(
        [
            {
                "id": "limit",
                "input": "Refund $600",
                "expected": "Escalate because amount is above the limit",
                "tags": {
                    "domain": "refund",
                    "action": "escalation",
                    "behavior": ["amount_above_limit", "escalation"],
                    "critical": True,
                },
            },
            {
                "id": "ambiguous",
                "input": "Refund $600 maybe, not sure",
                "expected": "Clarify ambiguous intent before refunding",
                "tags": {
                    "domain": "refund",
                    "action": "clarification",
                    "behavior": ["ambiguous_request", "confirmation_required"],
                    "critical": True,
                },
            },
        ]
    )
    result = analyze_suite(suite)
    states = {r.test_id: r.state for r in result.recommendations}
    assert states["limit"] != RecommendationState.MERGE
    assert states["ambiguous"] != RecommendationState.MERGE
    assert states["limit"] != RecommendationState.RETIRE
    assert states["ambiguous"] != RecommendationState.RETIRE
    for pair in result.pairs:
        assert pair.recommendation != RecommendationState.MERGE
        assert pair.recommendation != RecommendationState.RETIRE
