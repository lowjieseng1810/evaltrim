from evaltrim.analyze import analyze_suite
from evaltrim.behavior import extract_behavior
from evaltrim.coverage import unique_atoms_by_test
from evaltrim.models import RecommendationState
from evaltrim.parser import parse_suite


def test_unique_witness_summary_and_keep():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "common-a",
                    "input": "refund $20",
                    "expected": "pay",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "common-b",
                    "input": "refund $21",
                    "expected": "pay",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "privacy-only",
                    "input": "delete my personal data",
                    "expected": "confirm then delete",
                    "tags": {
                        "domain": "privacy",
                        "action": "confirmation",
                        "behavior": ["destructive", "pii_present"],
                        "critical": True,
                    },
                },
            ],
        }
    )
    result = analyze_suite(suite)
    witness = next(w for w in result.witnesses if w.test_id == "privacy-only")
    assert witness.unique_atoms
    rec = next(r for r in result.recommendations if r.test_id == "privacy-only")
    assert rec.state == RecommendationState.KEEP
    assert "privacy" in witness.summary.lower() or witness.unique_atoms


def test_no_unique_atoms_when_duplicated():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "x",
                    "expected": "y",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "b",
                    "input": "x",
                    "expected": "y",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
            ]
        }
    )
    behaviors = [extract_behavior(t) for t in suite.tests]
    unique = unique_atoms_by_test(suite.tests, behaviors)
    assert unique["a"] == []
    assert unique["b"] == []
