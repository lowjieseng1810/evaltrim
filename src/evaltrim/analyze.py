"""End-to-end analysis pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from evaltrim.behavior import extract_behavior
from evaltrim.coverage import compute_coverage, covers_declared, unique_atoms_by_test
from evaltrim.errors import TestNotFoundError
from evaltrim.llm.base import BehaviorExtractor
from evaltrim.models import (
    AnalysisResult,
    MaintenanceReport,
    RecommendationState,
    RedundantPair,
    SuiteSummary,
    TestEvidence,
    TestSuite,
    WitnessRecord,
)
from evaltrim.recommend import recommend
from evaltrim.scoring import value_score
from evaltrim.similarity import SimilarityEngine
from evaltrim.simulate import simulate_removal

METHODOLOGY = (
    "Scores are heuristics, not statistical guarantees. Redundancy is a weighted mix of "
    "TF-IDF cosine on inputs (semantic), Jaccard overlap of behavior atoms, TF-IDF cosine "
    "on expected oracles, and historical failure-rate closeness. Unique witnesses are "
    "behavior atoms observed in exactly one remaining test. Removal is simulated in memory "
    "and never deletes files. KEEP always wins over RETIRE when a test is the only witness "
    "for a critical behavior."
)


def analyze_suite(
    suite: TestSuite,
    *,
    extractor: BehaviorExtractor | None = None,
    pair_limit: int | None = None,
) -> AnalysisResult:
    tests = suite.tests
    declared = suite.critical_behaviors
    behaviors = [
        test.behavior
        or extract_behavior(test, declared_critical=declared, extractor=extractor)
        for test in tests
    ]
    # Attach extracted signatures onto copies for evidence.
    for test, behavior in zip(tests, behaviors, strict=True):
        test.behavior = behavior

    engine = SimilarityEngine(tests, behaviors, suite.config.weights)
    unique = unique_atoms_by_test(tests, behaviors)
    universe = {atom for b in behaviors for atom in b.atoms()}
    coverage = compute_coverage(tests, behaviors, declared_critical=declared, universe=universe)

    # Pairwise redundancy (upper triangle).
    pairs: list[RedundantPair] = []
    max_redundancy: dict[str, float] = {t.id: 0.0 for t in tests}
    partners: dict[str, list[str]] = defaultdict(list)
    oracle_conflicts: set[str] = set()
    n = len(tests)
    for i in range(n):
        for j in range(i + 1, n):
            raw = engine.pair_score(tests[i].id, tests[j].id)
            score = float(raw["score"])
            max_redundancy[tests[i].id] = max(max_redundancy[tests[i].id], score)
            max_redundancy[tests[j].id] = max(max_redundancy[tests[j].id], score)
            semantic = float(raw["semantic"])
            expected = float(raw["expected_similarity"])
            is_oracle_conflict = semantic >= 0.75 and expected <= 0.35
            if is_oracle_conflict:
                oracle_conflicts.add(tests[i].id)
                oracle_conflicts.add(tests[j].id)
            if score >= suite.config.redundancy_threshold or is_oracle_conflict:
                partners[tests[i].id].append(tests[j].id)
                partners[tests[j].id].append(tests[i].id)
                rec_state = (
                    RecommendationState.REVIEW
                    if is_oracle_conflict
                    else _pair_recommendation(
                        score=score,
                        unique_left=list(raw["unique_left"]),
                        unique_right=list(raw["unique_right"]),
                        expected=expected,
                        merge_threshold=suite.config.merge_threshold,
                        left_critical=behaviors[i].critical,
                        right_critical=behaviors[j].critical,
                    )
                )
                rationale = _pair_rationale(
                    rec_state, score, list(raw["shared"]), list(raw["unique_left"])
                )
                pairs.append(
                    RedundantPair(
                        left_id=tests[i].id,
                        right_id=tests[j].id,
                        score=score,
                        semantic=semantic,
                        behavior_overlap=float(raw["behavior_overlap"]),
                        expected_similarity=expected,
                        historical_overlap=float(raw["historical_overlap"]),
                        shared=list(raw["shared"]),
                        unique_left=list(raw["unique_left"]),
                        unique_right=list(raw["unique_right"]),
                        recommendation=rec_state,
                        rationale=rationale,
                    )
                )
    pairs.sort(key=lambda p: p.score, reverse=True)
    if pair_limit is not None:
        pairs = pairs[:pair_limit]

    conflict_ids = oracle_conflicts | _conflict_ids(pairs)
    max_cost = max(
        ((t.run_stats.estimated_cost_usd or 0.0) if t.run_stats else 0.0) for t in tests
    ) or 1.0

    evidence: list[TestEvidence] = []
    recommendations = []
    witnesses: list[WitnessRecord] = []
    for test, behavior in zip(tests, behaviors, strict=True):
        sim = simulate_removal(
            tests, behaviors, test.id, declared_critical=declared, baseline=coverage
        )
        uniq = unique.get(test.id, [])
        uniq_crit = _unique_critical(test.id, behavior, tests, behaviors, declared, uniq)
        score = value_score(
            test,
            behavior,
            unique_atoms=uniq,
            total_atoms=len(universe),
            max_cost=max_cost,
        )
        low_conf = behavior.confidence < 0.5 or (
            behavior.source == "heuristic" and behavior.domain == "unknown"
        )
        rec = recommend(
            test,
            unique_atoms=uniq,
            unique_critical=uniq_crit,
            redundancy_max=max_redundancy[test.id],
            merge_threshold=suite.config.merge_threshold,
            redundancy_threshold=suite.config.redundancy_threshold,
            simulation=sim,
            conflict=test.id in conflict_ids,
            stale=test.is_stale(stale_days=suite.config.stale_days),
            low_confidence=low_conf,
            value_score=score,
        )
        rec.pair_ids = partners.get(test.id, [])
        recommendations.append(rec)
        evidence.append(
            TestEvidence(
                test_id=test.id,
                behavior=behavior,
                unique_atoms=uniq,
                shared_atoms=sorted(set(behavior.atoms()) - set(uniq)),
                recommendation=rec,
                value_score=score,
                is_critical_witness=bool(uniq_crit) or (behavior.critical and bool(uniq)),
                redundancy_max=round(max_redundancy[test.id], 6),
                stale=test.is_stale(stale_days=suite.config.stale_days),
                conflict=test.id in conflict_ids,
            )
        )
        summary = (
            "Unique witness: " + ", ".join(_pretty(a) for a in uniq)
            if uniq
            else "No unique behavior atom; overlapping coverage."
        )
        witnesses.append(
            WitnessRecord(
                test_id=test.id,
                unique_atoms=uniq,
                unique_critical=uniq_crit,
                summary=summary,
                recommendation=rec.state,
            )
        )

    keep = sum(1 for r in recommendations if r.state == RecommendationState.KEEP)
    merge = sum(1 for r in recommendations if r.state == RecommendationState.MERGE)
    retire = sum(1 for r in recommendations if r.state == RecommendationState.RETIRE)
    review = sum(1 for r in recommendations if r.state == RecommendationState.REVIEW)
    reducible = merge + retire
    estimated = reducible / len(tests) if tests else 0.0

    summary = suite_summary_from(
        suite,
        keep=keep,
        merge=merge,
        retire=retire,
        review=review,
        estimated=estimated,
    )
    return AnalysisResult(
        summary=summary,
        coverage=coverage,
        evidence=evidence,
        pairs=pairs,
        witnesses=witnesses,
        recommendations=recommendations,
        conflicts=sorted(conflict_ids),
        methodology=METHODOLOGY,
    )


def suite_summary_from(suite: TestSuite, **counts: object) -> SuiteSummary:
    return SuiteSummary(
        name=suite.name,
        test_count=len(suite.tests),
        critical_test_count=sum(1 for t in suite.tests if t.tags.critical or (t.behavior and t.behavior.critical)),
        declared_critical_behaviors=list(suite.critical_behaviors),
        keep=int(counts.get("keep", 0)),
        merge=int(counts.get("merge", 0)),
        retire=int(counts.get("retire", 0)),
        review=int(counts.get("review", 0)),
        estimated_ci_reduction=float(counts.get("estimated", 0.0)),
    )


def build_maintenance(result: AnalysisResult) -> MaintenanceReport:
    merges = [p for p in result.pairs if p.recommendation == RecommendationState.MERGE]
    retirements = [r for r in result.recommendations if r.state == RecommendationState.RETIRE]
    stale = [e.test_id for e in result.evidence if e.stale]
    notes = [
        "EvalTrim never deletes or rewrites suite files.",
        "Treat RETIRE and MERGE as review queues, not automatic actions.",
    ]
    return MaintenanceReport(
        generated_at=datetime.now(UTC),
        summary=result.summary,
        coverage=result.coverage,
        candidate_merges=merges,
        candidate_retirements=retirements,
        stale_cases=stale,
        unique_witnesses=[w for w in result.witnesses if w.unique_atoms],
        critical_coverage=result.coverage.critical_coverage,
        estimated_suite_reduction=result.summary.estimated_ci_reduction,
        evidence=result.evidence,
        notes=notes,
    )


def _unique_critical(
    test_id: str,
    behavior,
    tests,
    behaviors,
    declared: list[str],
    unique_atoms: list[str],
) -> list[str]:
    declared_norm = {d.lower().replace(" ", "_") for d in declared}
    hits = []
    for name in declared_norm:
        holders = [
            t.id
            for t, b in zip(tests, behaviors, strict=True)
            if covers_declared(b, name)
        ]
        if holders == [test_id]:
            hits.append(name)
    if behavior.critical:
        crit_holders = [t.id for t, b in zip(tests, behaviors, strict=True) if b.critical]
        if crit_holders == [test_id]:
            hits.append("critical")
    for atom in unique_atoms:
        name = atom.split(":", 1)[-1]
        if name in declared_norm and name not in hits:
            hits.append(atom)
    return hits


def _conflict_ids(pairs: list[RedundantPair]) -> set[str]:
    ids: set[str] = set()
    for pair in pairs:
        if pair.semantic >= 0.75 and pair.expected_similarity <= 0.35:
            ids.add(pair.left_id)
            ids.add(pair.right_id)
    return ids


def _pair_recommendation(
    *,
    score: float,
    unique_left: list[str],
    unique_right: list[str],
    expected: float,
    merge_threshold: float,
    left_critical: bool,
    right_critical: bool,
) -> RecommendationState:
    meaningful_l = [a for a in unique_left if not a.startswith("state:")]
    meaningful_r = [a for a in unique_right if not a.startswith("state:")]
    if expected <= 0.35 and score >= 0.7:
        return RecommendationState.REVIEW
    if (left_critical or right_critical) and (meaningful_l or meaningful_r):
        return RecommendationState.KEEP
    if meaningful_l or meaningful_r:
        return RecommendationState.KEEP
    if score >= merge_threshold:
        return RecommendationState.MERGE
    return RecommendationState.REVIEW


def _pair_rationale(state: RecommendationState, score: float, shared: list[str], unique_left: list[str]) -> str:
    shared_s = ", ".join(_pretty(s) for s in shared[:8]) or "none"
    unique_s = ", ".join(_pretty(s) for s in unique_left[:6]) or "none"
    return (
        f"Possible duplicate: {score:.2f}. Shared: {shared_s}. "
        f"Unique (left): {unique_s}. Recommendation: {state.value}."
    )


def _pretty(atom: str) -> str:
    return atom.replace(":", "/").replace("_", " ")


def simulate_suite(suite: TestSuite, test_id: str):
    tests = suite.tests
    try:
        suite.get(test_id)
    except KeyError as exc:
        raise TestNotFoundError(f"Unknown test id: {test_id}") from exc
    declared = suite.critical_behaviors
    behaviors = [
        t.behavior or extract_behavior(t, declared_critical=declared) for t in tests
    ]
    for t, b in zip(tests, behaviors, strict=True):
        t.behavior = b
    return simulate_removal(tests, behaviors, test_id, declared_critical=declared)
