from evaltrim.analyze import analyze_suite, simulate_suite
from evaltrim.models import RecommendationState, Verdict
from evaltrim.parser import parse_suite


def test_removing_duplicate_is_safe():
    suite = parse_suite(
        {
            "tests": [
                {
                    "id": "a",
                    "input": "same",
                    "expected": "same",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "b",
                    "input": "same",
                    "expected": "same",
                    "tags": {"domain": "refund", "action": "execution", "behavior": ["amount_below_limit"]},
                },
            ]
        }
    )
    sim = simulate_suite(suite, "b")
    assert sim.verdict == Verdict.SAFE_TO_RETIRE
    assert sim.after_tests == 1
    assert not sim.lost_atoms


def test_removing_unique_critical_is_keep():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "refund",
                    "input": "refund $20",
                    "expected": "ok",
                    "tags": {"domain": "refund", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "privacy-delete",
                    "input": "wipe my data",
                    "expected": "confirm",
                    "tags": {
                        "domain": "privacy",
                        "action": "confirmation",
                        "behavior": ["destructive"],
                        "critical": True,
                    },
                },
            ],
        }
    )
    sim = simulate_suite(suite, "privacy-delete")
    assert sim.verdict == Verdict.KEEP
    assert sim.after_coverage.critical_coverage < sim.before_coverage.critical_coverage or sim.lost_atoms


def test_critical_unique_never_retired():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "dup-a",
                    "input": "hello there friend",
                    "expected": "greet",
                    "tags": {"domain": "support", "action": "apology"},
                    "metadata": {"stale": True},
                },
                {
                    "id": "dup-b",
                    "input": "hello there friend",
                    "expected": "greet",
                    "tags": {"domain": "support", "action": "apology"},
                    "metadata": {"stale": True},
                },
                {
                    "id": "only-privacy",
                    "input": "delete all personal data",
                    "expected": "require auth",
                    "tags": {
                        "domain": "privacy",
                        "behavior": ["destructive", "pii_present"],
                        "critical": True,
                    },
                    "metadata": {"stale": True},
                },
            ],
        }
    )
    result = analyze_suite(suite)
    rec = next(r for r in result.recommendations if r.test_id == "only-privacy")
    assert rec.state != RecommendationState.RETIRE
    assert rec.state == RecommendationState.KEEP
