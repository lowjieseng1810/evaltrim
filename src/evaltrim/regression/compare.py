"""Compare two analysis snapshots. Language is about suites, not live agent regressions."""

from __future__ import annotations

from evaltrim.models import AnalysisResult, RecommendationState


def compare_analysis(baseline: AnalysisResult, current: AnalysisResult) -> dict:
    b_ids = {e.test_id for e in baseline.evidence}
    c_ids = {e.test_id for e in current.evidence}
    added = sorted(c_ids - b_ids)
    removed = sorted(b_ids - c_ids)
    b_atoms = set()
    c_atoms = set()
    for e in baseline.evidence:
        b_atoms.update(e.behavior.atoms())
    for e in current.evidence:
        c_atoms.update(e.behavior.atoms())
    rec_b = {r.test_id: r.state for r in baseline.recommendations}
    rec_c = {r.test_id: r.state for r in current.recommendations}
    flipped = [
        {"id": tid, "from": rec_b[tid].value, "to": rec_c[tid].value}
        for tid in sorted(set(rec_b) & set(rec_c))
        if rec_b[tid] != rec_c[tid]
    ]
    risk = "LOW"
    if current.coverage.critical_coverage + 1e-9 < baseline.coverage.critical_coverage:
        risk = "HIGH"
    elif removed or any(x["to"] == RecommendationState.REVIEW.value for x in flipped):
        risk = "MEDIUM"
    return {
        "tests": {"before": len(b_ids), "after": len(c_ids), "added": added, "removed": removed},
        "critical_coverage": {
            "before": baseline.coverage.critical_coverage,
            "after": current.coverage.critical_coverage,
        },
        "behavior_atoms": {
            "before": len(b_atoms),
            "after": len(c_atoms),
            "new": sorted(c_atoms - b_atoms),
            "removed": sorted(b_atoms - c_atoms),
        },
        "recommendation_flips": flipped,
        "suite_diff_risk": risk,
        "note": (
            "This compares static suite analyses, not live agent behavior. "
            "A HIGH risk means declared critical coverage dropped in the suite snapshot."
        ),
    }
