"""Deterministic behavior signature extraction. LLM is optional and off by default."""

from __future__ import annotations

import re
from collections.abc import Mapping

from evaltrim.llm.base import BehaviorExtractor
from evaltrim.models import Behavior, TestCase

DOMAIN_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "refund": ("refund", "reimburse", "chargeback"),
    "payment": ("payment", "charge", "checkout", "invoice", "card"),
    "privacy": ("privacy", "gdpr", "delete my data", "pii", "personal data"),
    "authentication": ("login", "password", "auth", "2fa", "mfa", "sso"),
    "destructive_action": ("delete", "destroy", "wipe", "revoke", "cancel account"),
    "policy_violation": ("policy", "prohibited", "against the rules", "violation"),
    "shopping": ("cart", "order", "shipping", "sku", "product"),
    "coding": ("function", "refactor", "compile", "unit test", "pull request"),
    "support": ("ticket", "help desk", "customer"),
}

ACTION_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "escalation": ("escalate", "supervisor", "human agent", "tier 2"),
    "refusal": ("refuse", "cannot", "not allowed", "decline"),
    "confirmation": ("confirm", "are you sure", "double-check"),
    "execution": ("execute", "perform", "complete the", "apply"),
    "clarification": ("clarify", "which one", "more detail"),
    "apology": ("sorry", "apologize"),
    "tool_call": ("tool", "api", "function call"),
}

CONDITION_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "amount_above_limit": ("$600", "$700", "$1000", "above the limit", "exceeds", "over the limit"),
    "amount_at_limit": ("exactly", "at the limit", "boundary", "$500"),
    "amount_below_limit": ("below the limit", "under the limit", "$20", "$50"),
    "ambiguous_request": ("maybe", "not sure", "or maybe", "ambiguous", "unclear"),
    "confirmation_required": ("confirm", "are you sure"),
    "destructive": ("delete", "destroy", "irreversible"),
    "pii_present": ("ssn", "social security", "email", "phone number"),
    "unauthenticated": ("logged out", "anonymous", "without login"),
    "policy_boundary": ("policy limit", "exactly at"),
}

STATE_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "authenticated": ("logged in", "authenticated"),
    "unauthenticated": ("logged out", "guest", "anonymous"),
    "error": ("error", "failed", "timeout"),
    "normal": (),
}


def extract_behavior(
    test: TestCase,
    *,
    declared_critical: list[str] | None = None,
    extractor: BehaviorExtractor | None = None,
) -> Behavior:
    """Prefer explicit tags; otherwise deterministic keyword extraction."""
    declared_critical = declared_critical or []
    if _has_explicit_tags(test):
        behavior = _from_tags(test, declared_critical)
        behavior.source = "tags"
        behavior.confidence = 1.0
        return behavior

    if extractor is not None:
        llm_behavior = extractor.extract(test)
        if llm_behavior is not None:
            return llm_behavior

    return _from_text(test, declared_critical)


def _has_explicit_tags(test: TestCase) -> bool:
    tags = test.tags
    return bool(tags.domain or tags.action or tags.behavior or tags.conditions)


def _from_tags(test: TestCase, declared_critical: list[str]) -> Behavior:
    tags = test.tags
    conditions = list(tags.behavior) + list(tags.conditions)
    domain = (tags.domain or "unknown").lower().replace(" ", "_")
    action = (tags.action or _infer_action_from_conditions(conditions) or "unknown").lower()
    state = (tags.state or "normal").lower().replace(" ", "_")
    critical = bool(tags.critical) or _is_declared_critical(domain, action, conditions, declared_critical)
    return Behavior(
        domain=domain,
        action=action,
        conditions=conditions,
        state=state,
        critical=critical,
        source="tags",
        confidence=1.0,
    )


def _from_text(test: TestCase, declared_critical: list[str]) -> Behavior:
    blob = f"{test.input}\n{test.expected}".lower()
    domain = _first_match(blob, DOMAIN_KEYWORDS) or "unknown"
    action = _first_match(blob, ACTION_KEYWORDS) or "unknown"
    conditions = [name for name, needles in CONDITION_KEYWORDS.items() if any(n in blob for n in needles)]
    state = _first_match(blob, STATE_KEYWORDS) or "normal"
    amounts = re.findall(r"\$(\d+(?:,\d{3})*(?:\.\d+)?)", blob)
    if amounts:
        values = [float(a.replace(",", "")) for a in amounts]
        if any(v > 500 for v in values) and "amount_above_limit" not in conditions:
            conditions.append("amount_above_limit")
        if any(v == 500 for v in values) and "amount_at_limit" not in conditions:
            conditions.append("amount_at_limit")
        if any(v < 500 for v in values) and "amount_below_limit" not in conditions:
            conditions.append("amount_below_limit")
    critical = test.tags.critical or _is_declared_critical(domain, action, conditions, declared_critical)
    return Behavior(
        domain=domain,
        action=action,
        conditions=conditions,
        state=state,
        critical=critical,
        source="heuristic",
        confidence=0.7 if domain != "unknown" else 0.4,
    )


def _infer_action_from_conditions(conditions: list[str]) -> str | None:
    lowered = {c.lower() for c in conditions}
    if "escalation" in lowered:
        return "escalation"
    if "confirmation" in lowered or "confirmation_required" in lowered:
        return "confirmation"
    return None


def _is_declared_critical(
    domain: str,
    action: str,
    conditions: list[str],
    declared: list[str],
) -> bool:
    tokens = {domain, action, *conditions}
    declared_norm = {d.lower().replace(" ", "_") for d in declared}
    return any(token in declared_norm for token in tokens)


def _first_match(blob: str, table: Mapping[str, tuple[str, ...]]) -> str | None:
    for name, needles in table.items():
        if any(needle and needle in blob for needle in needles):
            return name
    return None
