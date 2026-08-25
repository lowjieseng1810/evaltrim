from evaltrim.behavior import extract_behavior
from evaltrim.models import Tags, TestCase


def test_explicit_tags_win():
    test = TestCase(
        id="t",
        input="hello",
        expected="world",
        tags=Tags(domain="refund", action="escalation", behavior=["amount_above_limit"], critical=True),
    )
    b = extract_behavior(test)
    assert b.domain == "refund"
    assert b.action == "escalation"
    assert "amount_above_limit" in b.conditions
    assert b.critical
    assert b.source == "tags"
    assert b.confidence == 1.0


def test_heuristic_from_text_is_deterministic():
    test = TestCase(
        id="t",
        input="I want a refund of $600",
        expected="Escalate request because it exceeds the limit.",
    )
    a = extract_behavior(test)
    b = extract_behavior(test)
    assert a == b
    assert a.domain == "refund"
    assert a.action == "escalation"
    assert "amount_above_limit" in a.conditions


def test_declared_critical_flags_matching_domain():
    test = TestCase(id="t", input="charge the card", expected="process payment")
    b = extract_behavior(test, declared_critical=["payment"])
    assert b.domain == "payment"
    assert b.critical
