"""Indexed removal must match compute_coverage-based reference safety."""

from pathlib import Path

from evaltrim.analyze import analyze_suite, simulate_suite
from evaltrim.behavior import extract_behavior
from evaltrim.boundary import classify_boundary, inject_boundary_atoms
from evaltrim.coverage import compute_coverage, covers_declared, unique_atoms_by_test
from evaltrim.models import Verdict
from evaltrim.parser import load_suite, parse_suite
from evaltrim.simulate import RemovalIndex, simulate_from_index


def _behaviors(suite):
    declared = suite.critical_behaviors
    behaviors = [t.behavior or extract_behavior(t, declared_critical=declared) for t in suite.tests]
    marks = {t.id: classify_boundary(t, limit=suite.config.policy_threshold) for t in suite.tests}
    behaviors = [inject_boundary_atoms(b, marks[t.id]) for t, b in zip(suite.tests, behaviors, strict=True)]
    return behaviors


def reference_safety(suite, test_id: str) -> dict:
    tests = suite.tests
    behaviors = _behaviors(suite)
    universe = {atom for b in behaviors for atom in b.atoms()}
    unique = unique_atoms_by_test(tests, behaviors)
    after = compute_coverage(
        tests,
        behaviors,
        declared_critical=suite.critical_behaviors,
        universe=universe,
        excluded_ids={test_id},
    )
    before = compute_coverage(tests, behaviors, declared_critical=suite.critical_behaviors, universe=universe)
    lost_atoms = list(unique.get(test_id, []))
    lost_critical = []
    for name in suite.critical_behaviors:
        holders = [t.id for t, b in zip(tests, behaviors, strict=True) if covers_declared(b, name)]
        if holders == [test_id]:
            lost_critical.append(name)
    if lost_critical or after.critical_coverage + 1e-9 < suite.config.policies.minimum_critical_coverage:
        if after.critical_coverage < before.critical_coverage - 1e-9 or lost_critical:
            verdict = Verdict.KEEP
        else:
            verdict = Verdict.KEEP
    elif [a for a in lost_atoms if not a.startswith("state:")]:
        verdict = Verdict.KEEP
    else:
        verdict = Verdict.SAFE_TO_RETIRE
        drop = before.behavior_coverage - after.behavior_coverage
        if drop > suite.config.policies.max_behavior_coverage_drop + 1e-12:
            verdict = Verdict.REVIEW
    return {
        "verdict": verdict,
        "lost_atoms": set(lost_atoms),
        "lost_critical": set(lost_critical),
        "critical_coverage": after.critical_coverage,
        "behavior_coverage": after.behavior_coverage,
    }


def assert_index_matches(suite) -> None:
    behaviors = _behaviors(suite)
    index = RemovalIndex.build(
        suite.tests,
        behaviors,
        declared_critical=suite.critical_behaviors,
        policies=suite.config.policies,
        suite=suite,
    )
    for test in suite.tests:
        indexed = simulate_from_index(index, test.id)
        ref = reference_safety(suite, test.id)
        keepish = {Verdict.KEEP, Verdict.REVIEW, Verdict.UNCERTAIN}
        if ref["verdict"] == Verdict.KEEP:
            assert indexed.verdict in keepish | {Verdict.KEEP}
        if indexed.verdict == Verdict.SAFE_TO_RETIRE:
            assert ref["verdict"] == Verdict.SAFE_TO_RETIRE
            assert not ref["lost_critical"]
            assert not [a for a in ref["lost_atoms"] if not a.startswith("state:")]
        assert indexed.after_coverage.critical_coverage == ref["critical_coverage"]
        assert indexed.after_coverage.behavior_coverage == ref["behavior_coverage"]
        assert set(indexed.lost_atoms) == ref["lost_atoms"]


def test_index_matches_demo():
    suite = load_suite(Path("examples/demo_suite.yaml"))
    assert_index_matches(suite)


def test_index_matches_constructed_suites():
    for path in (
        Path("benchmarks/coding_agent/suite.yaml"),
        Path("benchmarks/customer_support/suite.yaml"),
        Path("benchmarks/shopping_agent/suite.yaml"),
    ):
        assert_index_matches(load_suite(path))


def test_index_matches_generated_duplicates():
    suite = parse_suite(
        {
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": f"t{i}",
                    "input": "same prompt" if i % 3 else f"unique {i}",
                    "expected": "ok",
                    "tags": {
                        "domain": "privacy" if i == 0 else "refund",
                        "action": "execution",
                        "behavior": ["destructive"] if i == 0 else ["amount_below_limit"],
                        "critical": i == 0,
                    },
                }
                for i in range(12)
            ],
        }
    )
    assert_index_matches(suite)
    sim = simulate_suite(suite, "t0")
    assert sim.verdict == Verdict.KEEP


def test_analyze_uses_same_retirement_safety():
    suite = load_suite(Path("benchmarks/customer_support/suite.yaml"))
    result = analyze_suite(suite)
    for rec in result.recommendations:
        sim = simulate_suite(suite, rec.test_id)
        if rec.state.value == "RETIRE":
            assert sim.verdict == Verdict.SAFE_TO_RETIRE
