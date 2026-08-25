from evaltrim.analyze import analyze_suite
from evaltrim.models import RecommendationState
from evaltrim.parser import parse_suite


def test_conflicting_oracles_are_review():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "conflict-a",
                    "input": "Cancel my order 9981 and refund the card.",
                    "expected": "Cancel the order and issue a full refund immediately.",
                    "tags": {"domain": "refund", "action": "execution"},
                },
                {
                    "id": "conflict-b",
                    "input": "Cancel my order 9981 and refund the card.",
                    "expected": "Do not cancel. Escalate because fulfillment already started.",
                    "tags": {"domain": "refund", "action": "escalation"},
                },
            ]
        }
    )
    result = analyze_suite(suite)
    states = {r.test_id: r.state for r in result.recommendations}
    assert states["conflict-a"] == RecommendationState.REVIEW
    assert states["conflict-b"] == RecommendationState.REVIEW
    assert "conflict-a" in result.conflicts
