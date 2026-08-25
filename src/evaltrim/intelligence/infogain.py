"""Information gain of a test relative to the rest of the suite."""

from __future__ import annotations

from typing import Any

from evaltrim.models import AnalysisResult, TestSuite


def information_gain(suite: TestSuite, result: AnalysisResult) -> list[dict[str, Any]]:
    universe = {atom for e in result.evidence for atom in e.behavior.atoms()}
    reqs = {r.id for r in suite.requirements}
    families = {t.failure_family for t in suite.tests if t.failure_family}
    rows: list[dict[str, Any]] = []
    by_ev = {e.test_id: e for e in result.evidence}
    by_w = {w.test_id: w for w in result.witnesses}
    for test in suite.tests:
        ev = by_ev[test.id]
        w = by_w[test.id]
        new_atoms = len(w.unique_atoms)
        new_combo = 1 if w.unique_combo else 0
        new_bound = 1 if w.unique_boundary else 0
        new_req = len(w.unique_requirement)
        new_fam = 1 if w.unique_failure_family else 0
        score = new_atoms * 3 + new_combo * 2 + new_bound * 4 + new_req * 3 + new_fam * 3
        if ev.is_critical_witness:
            score += 8
        rows.append(
            {
                "test_id": test.id,
                "information_gain": float(score),
                "new_behavior_atoms": new_atoms,
                "new_combination": new_combo,
                "new_boundary": new_bound,
                "new_requirements": new_req,
                "new_failure_family": new_fam,
                "universe_atoms": len(universe),
                "suite_requirements": len(reqs),
                "suite_failure_families": len(families),
                "note": "Gain uses unique-witness counts, not a probabilistic entropy model.",
            }
        )
    rows.sort(key=lambda r: (-r["information_gain"], r["test_id"]))
    return rows
