"""Virtual test removal. Never mutates the suite on disk."""

from __future__ import annotations

from collections.abc import Sequence

from evaltrim.coverage import compute_coverage, unique_atoms_by_test
from evaltrim.models import Behavior, CoverageResult, RemovalSimulation, TestCase, Verdict


def simulate_removal(
    tests: Sequence[TestCase],
    behaviors: Sequence[Behavior],
    test_id: str,
    *,
    declared_critical: Sequence[str],
    baseline: CoverageResult | None = None,
) -> RemovalSimulation:
    ids = {t.id for t in tests}
    if test_id not in ids:
        raise KeyError(test_id)

    universe = {atom for b in behaviors for atom in b.atoms()}
    before = baseline or compute_coverage(
        tests, behaviors, declared_critical=declared_critical, universe=universe
    )
    after = compute_coverage(
        tests,
        behaviors,
        declared_critical=declared_critical,
        universe=universe,
        excluded_ids={test_id},
    )
    before_unique = unique_atoms_by_test(tests, behaviors)
    remaining = {
        atom
        for t, b in zip(tests, behaviors, strict=True)
        if t.id != test_id
        for atom in b.atoms()
    }
    lost_atoms = sorted(universe - remaining)
    lost_critical = list(after.uncovered_critical)

    lost_witnesses = []
    for tid, atoms in before_unique.items():
        if tid == test_id and atoms:
            lost_witnesses.extend(atoms)
        elif tid != test_id:
            continue
    # Newly unique atoms after removal are not losses.

    reasons: list[str] = []
    if lost_critical or after.critical_coverage < before.critical_coverage - 1e-9:
        verdict = Verdict.KEEP
        reasons.append("Removal reduces critical behavior coverage.")
        if lost_critical:
            reasons.append("Lost critical behaviors: " + ", ".join(lost_critical))
    elif lost_atoms:
        # Non-critical unique atoms still warrant KEEP unless they are only state/domain duplicates
        meaningful = [a for a in lost_atoms if not a.startswith("state:")]
        if meaningful:
            verdict = Verdict.KEEP
            reasons.append("Only remaining witness for: " + ", ".join(_human(a) for a in meaningful[:8]))
        else:
            verdict = Verdict.SAFE_TO_RETIRE
            reasons.append("Lost atoms are non-informative state markers only.")
    else:
        verdict = Verdict.SAFE_TO_RETIRE
        reasons.append("No behavior-atom or critical coverage loss.")

    return RemovalSimulation(
        test_id=test_id,
        before_tests=len(tests),
        after_tests=len(tests) - 1,
        before_coverage=before,
        after_coverage=after,
        lost_atoms=lost_atoms,
        lost_critical_atoms=lost_critical,
        lost_unique_witnesses=sorted(set(lost_witnesses)),
        verdict=verdict,
        reasons=reasons,
    )


def _human(atom: str) -> str:
    return atom.replace(":", "=").replace("_", " ")
