"""Classify unique witnesses. Semantic similarity never authorizes uniqueness."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evaltrim.models import Behavior, RemovalSimulation, TestCase

# Generic leftover bands. These may be unique by accident when sibling tests omit tags.
WEAK_CONDITIONS = frozenset({"amount_below_limit"})
WEAK_ATOM_PREFIXES = ("state:",)

WITNESS_KINDS = (
    "CRITICAL_UNIQUE",
    "BOUNDARY_UNIQUE",
    "REQUIREMENT_UNIQUE",
    "HISTORICAL_UNIQUE",
    "STRUCTURAL_UNIQUE",
    "BEHAVIORAL_UNIQUE",
    "WEAK_ACCIDENTAL",
    "DUPLICATE",
)


def signature_key(behavior: Behavior) -> tuple[str, str, tuple[str, ...], str]:
    return (
        (behavior.domain or "unknown").lower(),
        (behavior.action or "unknown").lower(),
        tuple(sorted(c.lower() for c in behavior.conditions)),
        (behavior.state or "normal").lower(),
    )


def unique_signatures(
    tests: list[TestCase], behaviors: list[Behavior]
) -> dict[str, tuple[str, str, tuple[str, ...], str]]:
    index: dict[tuple[str, str, tuple[str, ...], str], list[str]] = defaultdict(list)
    keys: dict[str, tuple[str, str, tuple[str, ...], str]] = {}
    for test, behavior in zip(tests, behaviors, strict=True):
        key = signature_key(behavior)
        keys[test.id] = key
        index[key].append(test.id)
    return {tid: keys[tid] for tid, key in keys.items() if len(index[key]) == 1}


def _weak_atom(atom: str) -> bool:
    if atom.startswith(WEAK_ATOM_PREFIXES):
        return True
    name = atom.split(":", 1)[-1]
    return name in WEAK_CONDITIONS


def distinctive_atoms(unique_atoms: list[str]) -> list[str]:
    return [a for a in unique_atoms if not _weak_atom(a)]


def classify_witness(
    *,
    test: TestCase,
    behavior: Behavior,
    unique_atoms: list[str],
    unique_critical: list[str],
    unique_boundary: bool,
    unique_requirement: list[str],
    unique_failure: bool,
    unique_failure_family: bool,
    unique_signature: bool,
    simulation: RemovalSimulation,
    conflict: bool = False,
    exact_input_conflict: bool = False,
) -> dict[str, Any]:
    """Coverage uniqueness is proven by counterfactual loss and exclusive signatures.

    Unique leftover generic atoms (e.g. amount_below_limit) are WEAK_ACCIDENTAL:
    they still block MERGE of hard negatives when distinctive, but they are not
    reported as suite unique witnesses.
    """
    distinctive = distinctive_atoms(unique_atoms)
    n_cond = len(behavior.conditions)
    strong_combo = unique_signature and n_cond >= 2
    non_weak_cond = any(c not in WEAK_CONDITIONS for c in behavior.conditions)
    lost_crit = bool(simulation.lost_critical_atoms)

    kinds: list[str] = []
    if unique_critical or lost_crit:
        kinds.append("CRITICAL_UNIQUE")
    if unique_boundary:
        kinds.append("BOUNDARY_UNIQUE")
    if unique_requirement:
        kinds.append("REQUIREMENT_UNIQUE")
    if unique_failure or unique_failure_family:
        kinds.append("HISTORICAL_UNIQUE")
    if unique_signature:
        kinds.append("STRUCTURAL_UNIQUE")
    if distinctive:
        kinds.append("BEHAVIORAL_UNIQUE")

    # Coverage witness = counterfactual critical/requirement/boundary/history loss
    # or an exclusive 2+ condition signature, or a critical test whose exclusive
    # signature is not a leftover generic band. Distinctive leftover atoms still
    # KEEP/anti-merge via unique_atoms in recommend(), but are not suite witnesses.
    explicit_ambiguity = any(c.lower() in {"ambiguous_request", "conflicting_instruction"} for c in behavior.conditions)
    is_coverage = bool(
        unique_critical
        or lost_crit
        or unique_boundary
        or unique_requirement
        or unique_failure
        or unique_failure_family
        or strong_combo
        or (unique_signature and non_weak_cond and test.tags.critical)
        or (unique_signature and explicit_ambiguity and test.tags.action in {"clarification", "confirmation"})
    )

    # Same-input oracle twins are not coverage witnesses unless counterfactual
    # critical/requirement loss is proven. Near-duplicate inputs with different
    # signatures (trajectory skip vs baseline) keep exclusive-signature coverage.
    if exact_input_conflict:
        is_coverage = bool(unique_critical or lost_crit or unique_requirement)
    elif conflict and not unique_signature:
        is_coverage = bool(unique_critical or lost_crit or unique_requirement or unique_boundary)
    if not kinds and not unique_atoms:
        kinds.append("DUPLICATE")
    elif not is_coverage and (unique_atoms or unique_signature):
        kinds.append("WEAK_ACCIDENTAL")

    if "CRITICAL_UNIQUE" in kinds:
        confidence = 0.99
    elif "REQUIREMENT_UNIQUE" in kinds or "BOUNDARY_UNIQUE" in kinds:
        confidence = 0.96
    elif "HISTORICAL_UNIQUE" in kinds:
        confidence = 0.93
    elif is_coverage and strong_combo:
        confidence = 0.92
    elif is_coverage:
        confidence = 0.88
    elif distinctive:
        confidence = 0.7
    else:
        confidence = 0.35

    is_critical_witness = bool(unique_critical or lost_crit or (is_coverage and test.tags.critical))
    false_critical = bool(is_critical_witness and not test.tags.critical)

    return {
        "kinds": kinds,
        "is_unique_witness": is_coverage,
        "is_critical_witness": is_critical_witness,
        "false_critical": false_critical,
        "witness_confidence": confidence,
        "distinctive_atoms": distinctive,
        "unique_signature": unique_signature,
        "evidence": {
            "unique_atoms": unique_atoms,
            "unique_critical": unique_critical,
            "unique_requirement": unique_requirement,
            "unique_boundary": unique_boundary,
            "unique_failure": unique_failure,
            "unique_failure_family": unique_failure_family,
            "lost_critical_atoms": list(simulation.lost_critical_atoms),
            "lost_atoms": list(simulation.lost_atoms),
            "counterfactual_verdict": simulation.verdict.value,
            "signature_unique": unique_signature,
            "n_conditions": n_cond,
        },
    }
