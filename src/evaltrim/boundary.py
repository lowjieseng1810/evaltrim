"""Boundary and malformed-input witnesses that must not be collapsed as duplicates."""

from __future__ import annotations

import re
from collections.abc import Sequence

from evaltrim.models import Behavior, TestCase
from evaltrim.normalize import extract_amounts

BOUNDARY_ATOMS = {
    "amount_at_limit",
    "amount_below_limit",
    "amount_above_limit",
    "policy_boundary",
    "empty_input",
    "malformed_value",
    "missing_field",
    "conflicting_instruction",
}


def classify_boundary(test: TestCase, *, limit: float = 500.0) -> list[str]:
    marks: list[str] = []
    text = f"{test.input}\n{test.expected}".lower()
    if not test.input.strip():
        marks.append("empty_input")
    if re.search(r"\{[a-z_]+\}|<\s*missing|null|n/?a\b", text):
        marks.append("missing_field")
    if re.search(r"[^\x20-\x7e]{3,}|\\\\x[0-9a-f]{2}|not a number|malformed", text):
        marks.append("malformed_value")
    if re.search(r"\b(or maybe|not sure|but also|ignore that|wait,)\b", text):
        marks.append("conflicting_instruction")
    amounts = extract_amounts(test.input)
    for amt in amounts:
        if abs(amt - limit) < 1e-9:
            marks.append("threshold_equality")
        elif 0 < (limit - amt) <= limit * 0.02 or abs(amt - (limit - 1)) < 1e-9:
            marks.append("just_below_threshold")
        elif 0 < (amt - limit) <= limit * 0.02 or abs(amt - (limit + 1)) < 1e-9:
            marks.append("just_above_threshold")
        marks.append(f"amount_{int(amt)}" if amt == int(amt) else f"amount_{amt}")
    tags = set(test.tags.behavior) | set(test.tags.conditions)
    if "policy_boundary" in tags or "amount_at_limit" in tags:
        marks.append("policy_boundary")
    # Dedupe
    seen: set[str] = set()
    out: list[str] = []
    for m in marks:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def inject_boundary_atoms(behavior: Behavior, marks: list[str]) -> Behavior:
    extra = [m for m in marks if m in BOUNDARY_ATOMS or m.startswith("just_") or m == "threshold_equality"]
    if not extra:
        return behavior
    conditions = list(behavior.conditions)
    for item in extra:
        if item not in conditions:
            conditions.append(item)
    return behavior.model_copy(update={"conditions": conditions})


def unique_boundary_ids(
    tests: Sequence[TestCase],
    marks_by_id: dict[str, list[str]],
) -> set[str]:
    index: dict[str, list[str]] = {}
    for test in tests:
        for mark in marks_by_id.get(test.id, []):
            if mark.startswith("amount_") and mark not in {
                "amount_above_limit",
                "amount_below_limit",
                "amount_at_limit",
            }:
                continue
            index.setdefault(mark, []).append(test.id)
    unique: set[str] = set()
    for mark, holders in index.items():
        if len(holders) == 1 and mark in {
            "threshold_equality",
            "just_below_threshold",
            "just_above_threshold",
            "empty_input",
            "malformed_value",
            "missing_field",
            "policy_boundary",
            "conflicting_instruction",
        }:
            unique.add(holders[0])
    return unique
