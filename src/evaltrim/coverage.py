"""Behavior coverage accounting over atomic signatures."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from evaltrim.models import Behavior, CoverageResult, TestCase

CRITICAL_ALIASES: dict[str, set[str]] = {
    "payment": {"payment", "refund"},
    "destructive_action": {"destructive_action", "destructive"},
    "privacy": {"privacy", "pii_present"},
    "authentication": {"authentication", "unauthenticated", "authenticated"},
    "policy_violation": {"policy_violation"},
}


def behavior_tokens(behavior: Behavior) -> set[str]:
    return {behavior.domain, behavior.action, behavior.state, *behavior.conditions}


def covers_declared(behavior: Behavior, declared_name: str) -> bool:
    name = declared_name.lower().replace(" ", "_")
    tokens = behavior_tokens(behavior)
    aliases = CRITICAL_ALIASES.get(name, {name})
    if tokens & aliases:
        return True
    if name == "critical" and behavior.critical:
        return True
    return False


def atom_index(behaviors: Sequence[Behavior]) -> dict[str, set[int]]:
    index: dict[str, set[int]] = defaultdict(set)
    for i, behavior in enumerate(behaviors):
        for atom in behavior.atoms():
            index[atom].add(i)
    return dict(index)


def critical_atoms_for(
    behaviors: Sequence[Behavior],
    declared: Sequence[str],
) -> set[str]:
    declared_norm = {d.lower().replace(" ", "_") for d in declared}
    atoms: set[str] = set()
    for behavior in behaviors:
        for atom in behavior.atoms():
            name = atom.split(":", 1)[-1]
            if behavior.critical or name in declared_norm:
                atoms.add(atom)
        if behavior.critical:
            atoms.add("flag:critical")
        if behavior.domain in declared_norm:
            atoms.add(f"domain:{behavior.domain}")
        if behavior.action in declared_norm:
            atoms.add(f"action:{behavior.action}")
        for cond in behavior.conditions:
            if cond in declared_norm:
                atoms.add(f"condition:{cond}")
    for name in declared_norm:
        # Include declared names even if no test currently maps them.
        atoms.add(f"declared:{name}")
    return atoms


def compute_coverage(
    tests: Sequence[TestCase],
    behaviors: Sequence[Behavior],
    *,
    declared_critical: Sequence[str],
    universe: Iterable[str] | None = None,
    critical_universe: Iterable[str] | None = None,
    excluded_ids: set[str] | None = None,
) -> CoverageResult:
    excluded_ids = excluded_ids or set()
    kept = [(t, b) for t, b in zip(tests, behaviors, strict=True) if t.id not in excluded_ids]
    observed = {atom for _, b in kept for atom in b.atoms()}
    all_atoms = set(universe) if universe is not None else {atom for b in behaviors for atom in b.atoms()}
    crit_universe = (
        set(critical_universe) if critical_universe is not None else critical_atoms_for(behaviors, declared_critical)
    )
    # Declared behaviors that no remaining test covers.
    covered_declared = set()
    declared_norm = {d.lower().replace(" ", "_") for d in declared_critical}
    for _, behavior in kept:
        tokens = {behavior.domain, behavior.action, *behavior.conditions}
        covered_declared.update(tokens & declared_norm)
        if behavior.critical:
            covered_declared.update(declared_norm & tokens)
            covered_declared.add("critical_flag")

    covered_critical = set()
    for _, behavior in kept:
        for atom in behavior.atoms():
            if atom in crit_universe:
                covered_critical.add(atom)
        name_hits = {behavior.domain, behavior.action, *behavior.conditions}
        for name in declared_norm:
            if name in name_hits or behavior.critical and name == "critical":
                covered_critical.add(f"declared:{name}")

    # Always treat observed critical-tagged tests as covering declared names they mention.
    behavior_coverage = (len(observed) / len(all_atoms)) if all_atoms else 1.0
    if crit_universe:
        # Coverage of declared names is the user-facing critical metric.
        if declared_norm:
            declared_covered = 0
            missing: list[str] = []
            for name in sorted(declared_norm):
                hit = any(covers_declared(b, name) for _, b in kept)
                if hit:
                    declared_covered += 1
                else:
                    missing.append(name)
            critical_coverage = declared_covered / len(declared_norm)
            uncovered_critical = missing
            critical_atoms = len(declared_norm)
            covered_critical_n = declared_covered
        else:
            critical_coverage = (
                1.0 if any(b.critical for _, b in kept) or not any(b.critical for b in behaviors) else 0.0
            )
            if any(b.critical for b in behaviors):
                remaining_crit = any(b.critical for _, b in kept)
                critical_coverage = 1.0 if remaining_crit else 0.0
            uncovered_critical = [] if critical_coverage == 1.0 else ["flag:critical"]
            critical_atoms = 1 if any(b.critical for b in behaviors) else 0
            covered_critical_n = 1 if critical_coverage == 1.0 and critical_atoms else 0
    else:
        critical_coverage = 1.0
        uncovered_critical = []
        critical_atoms = 0
        covered_critical_n = 0

    uncovered_behaviors = sorted(all_atoms - observed)
    return CoverageResult(
        behavior_atoms=len(all_atoms),
        covered_atoms=len(observed),
        behavior_coverage=round(behavior_coverage, 6),
        critical_atoms=critical_atoms,
        covered_critical_atoms=covered_critical_n,
        critical_coverage=round(critical_coverage, 6),
        uncovered_critical=uncovered_critical,
        uncovered_behaviors=uncovered_behaviors,
        critical_by_name={name: name not in uncovered_critical for name in declared_norm} if declared_norm else {},
    )


def unique_atoms_by_test(
    tests: Sequence[TestCase],
    behaviors: Sequence[Behavior],
    *,
    excluded_ids: set[str] | None = None,
) -> dict[str, list[str]]:
    excluded_ids = excluded_ids or set()
    index: dict[str, list[str]] = defaultdict(list)
    for test, behavior in zip(tests, behaviors, strict=True):
        if test.id in excluded_ids:
            continue
        for atom in behavior.atoms():
            index[atom].append(test.id)
    unique: dict[str, list[str]] = {t.id: [] for t in tests if t.id not in excluded_ids}
    for atom, holders in index.items():
        if len(holders) == 1:
            unique[holders[0]].append(atom)
    for test_id in unique:
        unique[test_id] = sorted(unique[test_id])
    return unique
