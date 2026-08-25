"""Virtual test removal. Never mutates the suite on disk."""

from __future__ import annotations

from collections.abc import Sequence

from evaltrim.coverage import compute_coverage, covers_declared, unique_atoms_by_test
from evaltrim.models import (
    Behavior,
    CoverageResult,
    RemovalSimulation,
    SafetyPolicies,
    TestCase,
    TestSuite,
    Verdict,
)


def simulate_removal(
    tests: Sequence[TestCase],
    behaviors: Sequence[Behavior],
    test_id: str,
    *,
    declared_critical: Sequence[str],
    baseline: CoverageResult | None = None,
    policies: SafetyPolicies | None = None,
    unique: dict[str, list[str]] | None = None,
    suite: TestSuite | None = None,
) -> RemovalSimulation:
    ids = {t.id for t in tests}
    if test_id not in ids:
        raise KeyError(test_id)

    policies = policies or SafetyPolicies()
    universe = {atom for b in behaviors for atom in b.atoms()}
    before = baseline or compute_coverage(tests, behaviors, declared_critical=declared_critical, universe=universe)
    unique = unique if unique is not None else unique_atoms_by_test(tests, behaviors)
    lost_atoms = list(unique.get(test_id, []))
    remaining_unique = sum(1 for tid, atoms in unique.items() if tid != test_id and atoms)
    unique_before = sum(1 for atoms in unique.values() if atoms)

    holders: dict[str, list[str]] = {name: [] for name in declared_critical}
    for test, behavior in zip(tests, behaviors, strict=True):
        for name in declared_critical:
            if covers_declared(behavior, name):
                holders[name].append(test.id)
    lost_critical = [name for name, ids_for in holders.items() if ids_for == [test_id]]

    after = before.model_copy(
        update={
            "covered_atoms": max(0, before.covered_atoms - len(lost_atoms)),
            "behavior_coverage": round(
                ((before.covered_atoms - len(lost_atoms)) / before.behavior_atoms) if before.behavior_atoms else 1.0,
                6,
            ),
            "uncovered_behaviors": sorted(set(before.uncovered_behaviors) | set(lost_atoms)),
            "uncovered_critical": sorted(set(before.uncovered_critical) | set(lost_critical)),
            "covered_critical_atoms": max(0, before.covered_critical_atoms - len(lost_critical)),
            "critical_coverage": round(
                (
                    (before.critical_atoms - len(set(before.uncovered_critical) | set(lost_critical)))
                    / before.critical_atoms
                )
                if before.critical_atoms
                else 1.0,
                6,
            ),
            "critical_by_name": {
                name: False if name in lost_critical else before.critical_by_name.get(name, True)
                for name in (before.critical_by_name or {n: True for n in declared_critical})
            },
        }
    )
    # Recompute coverage exactly when an atom or critical name is at risk so percentages stay honest.
    if lost_atoms or lost_critical:
        after = compute_coverage(
            tests,
            behaviors,
            declared_critical=declared_critical,
            universe=universe,
            excluded_ids={test_id},
        )

    drop = before.behavior_coverage - after.behavior_coverage
    reasons: list[str] = []
    if lost_critical or after.critical_coverage + 1e-9 < policies.minimum_critical_coverage:
        if after.critical_coverage < before.critical_coverage - 1e-9 or lost_critical:
            verdict = Verdict.KEEP
            reasons.append("Removal reduces critical behavior coverage.")
            if lost_critical:
                reasons.append("Lost critical behaviors: " + ", ".join(lost_critical))
        else:
            verdict = Verdict.KEEP
            reasons.append("Would violate minimum_critical_coverage policy.")
    elif lost_atoms:
        meaningful = [a for a in lost_atoms if not a.startswith("state:")]
        if meaningful:
            verdict = Verdict.KEEP
            reasons.append("Only remaining witness for: " + ", ".join(_human(a) for a in meaningful[:8]))
        else:
            verdict = Verdict.SAFE_TO_RETIRE
            reasons.append("Lost atoms are non-informative state markers only.")
    elif drop > policies.max_behavior_coverage_drop + 1e-12:
        verdict = Verdict.REVIEW
        reasons.append(
            f"Aggregate behavior coverage drop {drop:.4f} exceeds policy "
            f"max_behavior_coverage_drop={policies.max_behavior_coverage_drop}."
        )
    else:
        verdict = Verdict.SAFE_TO_RETIRE
        reasons.append("No unique behavior-atom or critical coverage loss.")

    lost_reqs: list[str] = []
    if suite is not None:
        for req in suite.requirements:
            req_holders = [t.id for t in tests if req.id in t.requirement_ids]
            if req_holders == [test_id]:
                lost_reqs.append(req.id)
                if req.critical:
                    verdict = Verdict.KEEP
                    reasons.append(f"Only remaining witness for critical requirement `{req.id}`.")
    hist = 0.0
    target = next((t for t in tests if t.id == test_id), None)
    if target and target.run_stats:
        hist = float(target.run_stats.failures)
    if hist > 0 and verdict == Verdict.SAFE_TO_RETIRE:
        verdict = Verdict.REVIEW
        reasons.append("Historical failures exist; removal is UNCERTAIN without review.")
    if target and target.behavior and target.behavior.source == "heuristic" and target.behavior.confidence < 0.5:
        if verdict == Verdict.SAFE_TO_RETIRE:
            verdict = Verdict.UNCERTAIN
            reasons.append("Behavior signature is low-confidence; counterfactual is UNCERTAIN.")

    evidence = {
        "unique_witnesses_lost": len(lost_atoms),
        "critical_coverage_lost": round(max(0.0, before.critical_coverage - after.critical_coverage), 6),
        "requirement_coverage_lost": len(lost_reqs),
        "historical_failure_contribution": hist,
        "counterfactual_coverage_loss": round(max(0.0, drop), 6),
        "verdict": verdict.value,
    }

    return RemovalSimulation(
        test_id=test_id,
        before_tests=len(tests),
        after_tests=len(tests) - 1,
        before_coverage=before,
        after_coverage=after,
        lost_atoms=lost_atoms,
        lost_critical_atoms=lost_critical,
        lost_unique_witnesses=sorted(set(lost_atoms)),
        unique_witnesses_before=unique_before,
        unique_witnesses_after=remaining_unique,
        critical_by_name_before=dict(before.critical_by_name),
        critical_by_name_after=dict(after.critical_by_name),
        lost_requirement_ids=lost_reqs,
        historical_failure_contribution=hist,
        counterfactual_coverage_loss=round(max(0.0, drop), 6),
        verdict=verdict,
        reasons=reasons,
        evidence=evidence,
    )


def _human(atom: str) -> str:
    return atom.replace(":", "=").replace("_", " ")
