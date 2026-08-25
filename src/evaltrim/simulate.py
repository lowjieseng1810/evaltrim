"""Virtual test removal. Never mutates the suite on disk.

Per-test impact is computed from precomputed coverage indexes so a suite of
n tests is O(n + atoms), not O(n²) full recomputes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

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

# Bump when incremental math changes so persisted analysis caches invalidate.
SIMULATION_VERSION = "0.6-index-2"


@dataclass
class RemovalIndex:
    """Precomputed holders for incremental counterfactual removal."""

    tests: list[TestCase]
    behaviors: list[Behavior]
    declared: list[str]
    policies: SafetyPolicies
    suite: TestSuite | None
    baseline: CoverageResult
    unique: dict[str, list[str]]
    universe: set[str]
    by_id: dict[str, TestCase]
    atom_holders: dict[str, set[str]]
    critical_holders: dict[str, set[str]]
    requirement_holders: dict[str, list[str]]
    unique_before: int
    tests_with_unique: int

    @staticmethod
    def build(
        tests: Sequence[TestCase],
        behaviors: Sequence[Behavior],
        *,
        declared_critical: Sequence[str],
        baseline: CoverageResult | None = None,
        policies: SafetyPolicies | None = None,
        unique: dict[str, list[str]] | None = None,
        suite: TestSuite | None = None,
    ) -> RemovalIndex:
        policies = policies or SafetyPolicies()
        universe = {atom for b in behaviors for atom in b.atoms()}
        before = baseline or compute_coverage(tests, behaviors, declared_critical=declared_critical, universe=universe)
        unique = unique if unique is not None else unique_atoms_by_test(tests, behaviors)
        atom_holders: dict[str, set[str]] = defaultdict(set)
        for test, behavior in zip(tests, behaviors, strict=True):
            for atom in behavior.atoms():
                atom_holders[atom].add(test.id)
        critical_holders: dict[str, set[str]] = defaultdict(set)
        for name in declared_critical:
            for test, behavior in zip(tests, behaviors, strict=True):
                if covers_declared(behavior, name):
                    critical_holders[name].add(test.id)
        req_holders: dict[str, list[str]] = defaultdict(list)
        if suite is not None:
            for req in suite.requirements:
                req_holders[req.id] = [t.id for t in tests if req.id in t.requirement_ids]
        return RemovalIndex(
            tests=list(tests),
            behaviors=list(behaviors),
            declared=list(declared_critical),
            policies=policies,
            suite=suite,
            baseline=before,
            unique=unique,
            universe=universe,
            by_id={t.id: t for t in tests},
            atom_holders=dict(atom_holders),
            critical_holders=dict(critical_holders),
            requirement_holders=dict(req_holders),
            unique_before=sum(1 for atoms in unique.values() if atoms),
            tests_with_unique=sum(1 for atoms in unique.values() if atoms),
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
    index: RemovalIndex | None = None,
) -> RemovalSimulation:
    if index is None:
        index = RemovalIndex.build(
            tests,
            behaviors,
            declared_critical=declared_critical,
            baseline=baseline,
            policies=policies,
            unique=unique,
            suite=suite,
        )
    return simulate_from_index(index, test_id)


def simulate_from_index(index: RemovalIndex, test_id: str) -> RemovalSimulation:
    if test_id not in index.by_id:
        raise KeyError(test_id)
    policies = index.policies
    before = index.baseline
    lost_atoms = list(index.unique.get(test_id, []))
    remaining_unique = index.tests_with_unique - (1 if lost_atoms else 0)
    lost_critical = [
        name for name, holders in index.critical_holders.items() if len(holders) == 1 and test_id in holders
    ]

    after = _after_coverage(index, test_id, lost_atoms, lost_critical)
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
    if index.suite is not None:
        for req in index.suite.requirements:
            holders = index.requirement_holders.get(req.id, [])
            if holders == [test_id]:
                lost_reqs.append(req.id)
                if req.critical:
                    verdict = Verdict.KEEP
                    reasons.append(f"Only remaining witness for critical requirement `{req.id}`.")
    hist = 0.0
    target = index.by_id[test_id]
    if target.run_stats:
        hist = float(target.run_stats.failures)
    if hist > 0 and verdict == Verdict.SAFE_TO_RETIRE:
        verdict = Verdict.REVIEW
        reasons.append("Historical failures exist; removal is UNCERTAIN without review.")
    if target.behavior and target.behavior.source == "heuristic" and target.behavior.confidence < 0.5:
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
        "simulation_version": SIMULATION_VERSION,
    }
    return RemovalSimulation(
        test_id=test_id,
        before_tests=len(index.tests),
        after_tests=len(index.tests) - 1,
        before_coverage=before,
        after_coverage=after,
        lost_atoms=lost_atoms,
        lost_critical_atoms=lost_critical,
        lost_unique_witnesses=sorted(set(lost_atoms)),
        unique_witnesses_before=index.unique_before,
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


def _after_coverage(
    index: RemovalIndex,
    test_id: str,
    lost_atoms: list[str],
    lost_critical: list[str],
) -> CoverageResult:
    declared_norm = {d.lower().replace(" ", "_") for d in index.declared}
    all_atoms = index.universe
    lost_set = set(lost_atoms)
    remaining_n = len(all_atoms) - len(lost_set)
    behavior_coverage = (remaining_n / len(all_atoms)) if all_atoms else 1.0
    uncovered_critical: list[str] = []
    covered_critical_n = 0
    critical_atoms = 0
    if declared_norm:
        critical_atoms = len(declared_norm)
        for orig in index.declared:
            name = orig.lower().replace(" ", "_")
            holders = index.critical_holders.get(orig) or set()
            still = len(holders) > 1 or (len(holders) == 1 and test_id not in holders)
            if still:
                covered_critical_n += 1
            else:
                uncovered_critical.append(name)
        # Dedupe if declared list had mixed-case duplicates.
        uncovered_critical = sorted(set(uncovered_critical))
        covered_critical_n = critical_atoms - len(uncovered_critical)
        critical_coverage = covered_critical_n / critical_atoms if critical_atoms else 1.0
    else:
        remaining_crit = any(b.critical and t.id != test_id for t, b in zip(index.tests, index.behaviors, strict=True))
        any_crit = any(b.critical for b in index.behaviors)
        critical_coverage = 1.0 if remaining_crit or not any_crit else 0.0
        uncovered_critical = [] if critical_coverage == 1.0 else ["flag:critical"]
        critical_atoms = 1 if any_crit else 0
        covered_critical_n = 1 if critical_coverage == 1.0 and critical_atoms else 0

    return CoverageResult(
        behavior_atoms=len(all_atoms),
        covered_atoms=remaining_n,
        behavior_coverage=round(behavior_coverage, 6),
        critical_atoms=critical_atoms,
        covered_critical_atoms=covered_critical_n,
        critical_coverage=round(critical_coverage, 6),
        uncovered_critical=uncovered_critical,
        uncovered_behaviors=sorted(lost_set),
        critical_by_name={name: name not in uncovered_critical for name in declared_norm} if declared_norm else {},
    )


def _human(atom: str) -> str:
    return atom.replace(":", "=").replace("_", " ")
