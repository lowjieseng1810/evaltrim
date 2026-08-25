"""Turn a production failure into a candidate test that must earn a place in the suite."""

from __future__ import annotations

from typing import Any

from evaltrim.analyze import analyze_suite
from evaltrim.behavior import extract_behavior
from evaltrim.models import RecommendationState, Tags, TestCase, TestSuite


def candidate_from_failure(record: dict[str, Any]) -> TestCase:
    ident = str(record.get("id") or record.get("test_id") or "prod-failure")
    inp = str(record.get("input") or record.get("prompt") or record.get("user") or "")
    expected = str(
        record.get("expected")
        or record.get("desired")
        or record.get("oracle")
        or "Review the failing production trajectory."
    )
    tags_raw = record.get("tags") if isinstance(record.get("tags"), dict) else {}
    return TestCase(
        id=ident,
        input=inp,
        expected=expected,
        tags=Tags.model_validate(tags_raw) if tags_raw else Tags(),
        metadata={"source": "production_failure", "raw": {k: record[k] for k in record if k != "tags"}},
        requirement_ids=list(record.get("requirement_ids") or []),
        provenance_files=list(record.get("provenance_files") or []),
        tool_dependencies=list(record.get("tool_dependencies") or []),
        failure_family=record.get("failure_family"),
    )


def evaluate_failure_candidate(suite: TestSuite, candidate: TestCase) -> dict[str, Any]:
    """Run the candidate through uniqueness/redundancy/oracle review. Do not append blindly."""
    if any(t.id == candidate.id for t in suite.tests):
        candidate = candidate.model_copy(update={"id": candidate.id + "-candidate"})
    candidate.behavior = extract_behavior(candidate, declared_critical=suite.critical_behaviors)
    extended = suite.model_copy(update={"tests": [*suite.tests, candidate]})
    result = analyze_suite(extended)
    rec = next(r for r in result.recommendations if r.test_id == candidate.id)
    wit = next(w for w in result.witnesses if w.test_id == candidate.id)
    unique = bool(wit.unique_atoms or wit.unique_critical or wit.unique_requirement or wit.unique_boundary)
    redundant = rec.state in {RecommendationState.MERGE, RecommendationState.RETIRE}
    if unique:
        decision = RecommendationState.ADD_CANDIDATE
        reason = "Candidate adds a unique witness (behavior, boundary, requirement, or critical)."
    elif rec.state == RecommendationState.REVIEW or candidate.id in result.conflicts:
        decision = RecommendationState.REVIEW
        reason = "Candidate overlaps an existing region or has an oracle conflict; review before adding."
    elif redundant:
        decision = RecommendationState.KEEP
        reason = "Candidate is redundant with existing coverage; do not append."
    else:
        decision = RecommendationState.ADD_CANDIDATE
        reason = "Candidate is not a unique witness but is not a duplicate; queue for human add."
    return {
        "candidate_id": candidate.id,
        "decision": decision.value,
        "reason": reason,
        "unique": unique,
        "recommendation": rec.model_dump(mode="json"),
        "evidence": rec.evidence.model_dump(mode="json") if rec.evidence else None,
        "note": "EvalTrim never appends production failures automatically.",
    }


def compress_production_failures(records: list[dict[str, Any]], suite: TestSuite | None = None) -> dict[str, Any]:
    """Cluster failures into families, then unique witnesses. Never auto-inserts tests."""
    from collections import defaultdict

    from evaltrim.normalize import normalize_text

    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        fam = rec.get("failure_family")
        if not fam:
            key = normalize_text(str(rec.get("input") or rec.get("error") or rec.get("id") or ""))
            fam = key[:48] or "unknown"
        families[str(fam)].append(rec)
    unique_witnesses = []
    for fam, members in families.items():
        representative = members[0]
        unique_witnesses.append(
            {
                "failure_family": fam,
                "size": len(members),
                "representative_id": representative.get("id"),
            }
        )
    covered = 0
    if suite is not None:
        existing = {t.failure_family for t in suite.tests if t.failure_family}
        covered = sum(1 for fam in families if fam in existing)
    n = len(records)
    n_fam = len(families)
    n_wit = len(unique_witnesses)
    return {
        "production_failures": n,
        "failure_families": n_fam,
        "unique_regression_witnesses": n_wit,
        "already_covered_families": covered,
        "compression_ratio": round(n_wit / n, 6) if n else 1.0,
        "families": unique_witnesses,
        "note": "Compression is clustering, not automatic suite insertion.",
    }
