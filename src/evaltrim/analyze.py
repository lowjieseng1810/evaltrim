"""End-to-end analysis pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from time import perf_counter

from evaltrim.behavior import extract_behavior
from evaltrim.boundary import classify_boundary, inject_boundary_atoms, unique_boundary_ids
from evaltrim.candidates import CandidatePairGenerator
from evaltrim.coverage import compute_coverage, covers_declared, unique_atoms_by_test
from evaltrim.embeddings import load_encoder
from evaltrim.errors import TestNotFoundError
from evaltrim.lifecycle import infer_lifecycle, stale_status
from evaltrim.llm.base import BehaviorExtractor
from evaltrim.models import (
    AnalysisResult,
    MaintenanceReport,
    OracleStatus,
    RecommendationState,
    RedundancyDecision,
    RedundantPair,
    RequirementCoverage,
    SafetyPolicies,
    SuiteSummary,
    TestEvidence,
    TestSuite,
    WitnessRecord,
)
from evaltrim.oracle import analyze_oracles
from evaltrim.recommend import recommend
from evaltrim.scoring import value_score
from evaltrim.similarity import SimilarityEngine
from evaltrim.simulate import simulate_removal

METHODOLOGY = (
    "Scores are heuristics, not statistical guarantees. Semantic similarity combines "
    "normalized-token TF-IDF, character n-grams, and raw TF-IDF. Optional hashing embeddings "
    "or an LLM comparator may be enabled explicitly. Redundancy also uses Jaccard overlap of "
    "behavior atoms, expected-oracle similarity, and historical failure-rate closeness. "
    "Candidate generation uses full pairwise comparison below config.full_pairwise_limit and "
    "blocking (exact hash, behavior signature, inverted-index neighbors) above it. Unique "
    "witnesses include singleton atoms, unique condition combinations, and boundary marks. "
    "Removal is simulated in memory and never deletes files. KEEP always wins over RETIRE when "
    "a test is the only witness for a critical behavior. A high semantic score alone never retires."
)


def analyze_suite(
    suite: TestSuite,
    *,
    extractor: BehaviorExtractor | None = None,
    pair_limit: int | None = None,
) -> AnalysisResult:
    t0 = perf_counter()
    tests = suite.tests
    declared = suite.critical_behaviors
    cfg = suite.config
    policies = cfg.policies or SafetyPolicies()

    t_beh = perf_counter()
    behaviors = [
        test.behavior or extract_behavior(test, declared_critical=declared, extractor=extractor) for test in tests
    ]
    marks_by_id = {test.id: classify_boundary(test, limit=cfg.policy_threshold) for test in tests}
    behaviors = [inject_boundary_atoms(b, marks_by_id[t.id]) for t, b in zip(tests, behaviors, strict=True)]
    for test, behavior in zip(tests, behaviors, strict=True):
        test.behavior = behavior
    behavior_s = perf_counter() - t_beh

    encoder = load_encoder(enabled=cfg.embeddings_enabled, persist=cfg.persist_embedding_cache)
    engine = SimilarityEngine(tests, behaviors, cfg.weights, encoder=encoder)
    unique = unique_atoms_by_test(tests, behaviors)
    universe = {atom for b in behaviors for atom in b.atoms()}
    coverage = compute_coverage(tests, behaviors, declared_critical=declared, universe=universe)
    boundary_unique = unique_boundary_ids(tests, marks_by_id)
    combo_unique = _unique_combos(tests, behaviors)
    failure_unique = _unique_failures(tests)

    t_cand = perf_counter()
    generator = CandidatePairGenerator(
        full_pairwise_limit=cfg.full_pairwise_limit,
        neighbor_k=cfg.candidate_neighbor_k,
    )
    index_pairs = generator.pairs(tests, behaviors)
    candidate_s = perf_counter() - t_cand

    pairs: list[RedundantPair] = []
    max_redundancy: dict[str, float] = {t.id: 0.0 for t in tests}
    partners: dict[str, list[str]] = defaultdict(list)
    semantic_triples: list[tuple[str, str, float, float]] = []

    t_sim = perf_counter()
    for i, j in index_pairs:
        raw = engine.pair_score(tests[i].id, tests[j].id)
        score = float(raw["score"])
        max_redundancy[tests[i].id] = max(max_redundancy[tests[i].id], score)
        max_redundancy[tests[j].id] = max(max_redundancy[tests[j].id], score)
        semantic = float(raw["semantic"])
        expected = float(raw["expected_similarity"])
        semantic_triples.append((tests[i].id, tests[j].id, semantic, expected))
        decision = _decision(
            score=score,
            semantic=semantic,
            overlap=float(raw["behavior_overlap"]),
            expected=expected,
            historical=float(raw["historical_overlap"]),
            unique_left=list(raw["unique_left"]),
            unique_right=list(raw["unique_right"]),
            left_critical=behaviors[i].critical,
            right_critical=behaviors[j].critical,
            merge_threshold=cfg.merge_threshold,
            boundary_l=tests[i].id in boundary_unique,
            boundary_r=tests[j].id in boundary_unique,
        )
        is_oracle_conflict = decision.conflict
        if score >= cfg.redundancy_threshold or is_oracle_conflict:
            partners[tests[i].id].append(tests[j].id)
            partners[tests[j].id].append(tests[i].id)
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
                    recommendation=decision.recommendation,
                    rationale=decision.reasons[0] if decision.reasons else decision.label,
                    decision=decision,
                )
            )
    similarity_s = perf_counter() - t_sim
    pairs.sort(key=lambda p: p.score, reverse=True)
    if pair_limit is not None:
        pairs = pairs[:pair_limit]

    oracle_health, oracle_conflicts, conflict_ids = analyze_oracles(
        tests,
        behaviors,
        stale_days=cfg.stale_days,
        semantic_pairs=semantic_triples,
    )
    conflict_ids = set(conflict_ids)
    health_by_id = {h.test_id: h for h in oracle_health}
    max_cost = max(((t.run_stats.estimated_cost_usd or 0.0) if t.run_stats else 0.0) for t in tests) or 1.0

    t_rem = perf_counter()
    evidence: list[TestEvidence] = []
    recommendations = []
    witnesses: list[WitnessRecord] = []
    for test, behavior in zip(tests, behaviors, strict=True):
        sim = simulate_removal(
            tests,
            behaviors,
            test.id,
            declared_critical=declared,
            baseline=coverage,
            policies=policies,
            unique=unique,
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
        low_conf = behavior.confidence < 0.5 or (behavior.source == "heuristic" and behavior.domain == "unknown")
        life = infer_lifecycle(test, conflict=test.id in conflict_ids, stale_days=cfg.stale_days)
        rec = recommend(
            test,
            unique_atoms=uniq,
            unique_critical=uniq_crit,
            redundancy_max=max_redundancy[test.id],
            merge_threshold=cfg.merge_threshold,
            redundancy_threshold=cfg.redundancy_threshold,
            simulation=sim,
            conflict=test.id in conflict_ids,
            stale=test.is_stale(stale_days=cfg.stale_days),
            low_confidence=low_conf,
            value_score=score,
            boundary_unique=test.id in boundary_unique,
            unique_combo=test.id in combo_unique,
            oracle_status=(health_by_id[test.id].status if test.id in health_by_id else OracleStatus.TRUSTED),
            lifecycle=life,
            policies=policies,
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
                stale=test.is_stale(stale_days=cfg.stale_days),
                conflict=test.id in conflict_ids,
                lifecycle=life.value,
                stale_status=stale_status(test, stale_days=cfg.stale_days).value,
            )
        )
        extra = []
        if test.id in combo_unique:
            extra.append("unique condition combination")
        if test.id in failure_unique:
            extra.append("unique failure history")
        witness_summary = (
            "Unique witness: " + ", ".join(_pretty(a) for a in uniq)
            if uniq
            else "No unique behavior atom; overlapping coverage."
        )
        if extra:
            witness_summary += " (" + ", ".join(extra) + ")"
        witnesses.append(
            WitnessRecord(
                test_id=test.id,
                unique_atoms=uniq,
                unique_critical=uniq_crit,
                summary=witness_summary,
                recommendation=rec.state,
                boundary_marks=marks_by_id.get(test.id, []),
                unique_combo=test.id in combo_unique,
                unique_failure=test.id in failure_unique,
            )
        )
    removal_s = perf_counter() - t_rem

    keep = sum(1 for r in recommendations if r.state == RecommendationState.KEEP)
    merge = sum(1 for r in recommendations if r.state == RecommendationState.MERGE)
    retire = sum(1 for r in recommendations if r.state == RecommendationState.RETIRE)
    review = sum(1 for r in recommendations if r.state == RecommendationState.REVIEW)
    reducible = merge + retire
    estimated = reducible / len(tests) if tests else 0.0
    req_cov = _requirement_coverage(suite)

    summary = suite_summary_from(
        suite,
        keep=keep,
        merge=merge,
        retire=retire,
        review=review,
        estimated=estimated,
    )
    total = perf_counter() - t0
    return AnalysisResult(
        summary=summary,
        coverage=coverage,
        evidence=evidence,
        pairs=pairs,
        witnesses=witnesses,
        recommendations=recommendations,
        conflicts=sorted(conflict_ids),
        methodology=METHODOLOGY,
        oracle_health=oracle_health,
        oracle_conflicts=oracle_conflicts,
        requirement_coverage=req_cov,
        timings={
            "behavior_seconds": round(behavior_s, 6),
            "candidate_seconds": round(candidate_s, 6),
            "similarity_seconds": round(similarity_s, 6),
            "removal_seconds": round(removal_s, 6),
            "total_seconds": round(total, 6),
        },
        candidate_pairs_considered=len(index_pairs),
        embeddings_used=encoder is not None,
        llm_used=extractor is not None or cfg.llm_enabled,
    )


def suite_summary_from(
    suite: TestSuite,
    *,
    keep: int = 0,
    merge: int = 0,
    retire: int = 0,
    review: int = 0,
    estimated: float = 0.0,
) -> SuiteSummary:
    return SuiteSummary(
        name=suite.name,
        test_count=len(suite.tests),
        critical_test_count=sum(1 for t in suite.tests if t.tags.critical or (t.behavior and t.behavior.critical)),
        declared_critical_behaviors=list(suite.critical_behaviors),
        keep=keep,
        merge=merge,
        retire=retire,
        review=review,
        estimated_ci_reduction=estimated,
    )


def build_maintenance(result: AnalysisResult) -> MaintenanceReport:
    merges = [p for p in result.pairs if p.recommendation == RecommendationState.MERGE]
    retirements = [r for r in result.recommendations if r.state == RecommendationState.RETIRE]
    stale = [e.test_id for e in result.evidence if e.stale]
    notes = [
        "EvalTrim never deletes or rewrites suite files.",
        "Treat RETIRE and MERGE as review queues, not automatic actions.",
        "Stale unique critical witnesses stay KEEP.",
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
        requirement_coverage=result.requirement_coverage,
    )


def _requirement_coverage(suite: TestSuite) -> list[RequirementCoverage]:
    rows: list[RequirementCoverage] = []
    for req in suite.requirements:
        holders = [t.id for t in suite.tests if req.id in t.requirement_ids]
        rows.append(
            RequirementCoverage(
                requirement_id=req.id,
                description=req.description,
                critical=req.critical,
                covered_by=holders,
                uncovered=len(holders) == 0,
            )
        )
    return rows


def _unique_combos(tests, behaviors) -> set[str]:
    index: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for test, behavior in zip(tests, behaviors, strict=True):
        key = tuple(sorted(behavior.conditions))
        if key:
            index[key].append(test.id)
    return {ids[0] for ids in index.values() if len(ids) == 1}


def _unique_failures(tests) -> set[str]:
    failed = [t.id for t in tests if t.run_stats and t.run_stats.failures > 0]
    return set(failed) if len(failed) == 1 else set()


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
        holders = [t.id for t, b in zip(tests, behaviors, strict=True) if covers_declared(b, name)]
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


def _decision(
    *,
    score: float,
    semantic: float,
    overlap: float,
    expected: float,
    historical: float,
    unique_left: list[str],
    unique_right: list[str],
    left_critical: bool,
    right_critical: bool,
    merge_threshold: float,
    boundary_l: bool,
    boundary_r: bool,
) -> RedundancyDecision:
    meaningful_l = [a for a in unique_left if not a.startswith("state:")]
    meaningful_r = [a for a in unique_right if not a.startswith("state:")]
    conflict = semantic >= 0.75 and expected <= 0.35
    unique = meaningful_l + meaningful_r
    critical = left_critical or right_critical
    boundary = boundary_l or boundary_r
    reasons: list[str] = []
    if conflict:
        state = RecommendationState.REVIEW
        reasons.append("Oracle conflict: similar inputs, dissimilar expected.")
        confidence = 0.55
        label = "ORACLE_CONFLICT"
    elif boundary and (boundary_l != boundary_r or meaningful_l or meaningful_r):
        state = RecommendationState.KEEP
        reasons.append("Boundary uniqueness: do not collapse threshold neighbors.")
        confidence = 0.95
        label = "BOUNDARY_KEEP"
    elif unique or (critical and (meaningful_l or meaningful_r)):
        state = RecommendationState.KEEP
        reasons.append("Unique behavior remains on at least one side.")
        confidence = 0.9
        label = "KEEP_BOTH"
    elif score >= merge_threshold and overlap >= 0.99 and expected >= 0.8 and not unique:
        state = RecommendationState.MERGE
        reasons.append("REDUNDANT_CANDIDATE: high overlap on semantics, behavior, and expected; no unique atom.")
        confidence = min(0.93, 0.5 + 0.5 * score)
        label = "REDUNDANT_CANDIDATE"
    elif semantic >= merge_threshold and overlap < 0.5:
        state = RecommendationState.KEEP
        reasons.append("High semantic score alone is not sufficient; behavior overlap is low.")
        confidence = 0.85
        label = "SEMANTIC_ONLY_KEEP"
    else:
        state = RecommendationState.REVIEW
        reasons.append("Possible duplicate below merge confidence.")
        confidence = 0.6
        label = "REVIEW"
    reasons.append(
        f"Evidence: semantic={semantic:.2f} behavior_overlap={overlap:.2f} "
        f"expected={expected:.2f} historical={historical:.2f} unique={unique or 'none'} "
        f"critical={critical} boundary_unique={boundary}."
    )
    return RedundancyDecision(
        label=label,
        semantic_similarity=semantic,
        behavior_overlap=overlap,
        expected_behavior_similarity=expected,
        historical_overlap=historical,
        unique_behavior=unique,
        critical_behavior=critical,
        boundary_unique=boundary,
        conflict=conflict,
        decision_confidence=round(confidence, 4),
        recommendation=state,
        reasons=reasons,
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
    behaviors = [t.behavior or extract_behavior(t, declared_critical=declared) for t in tests]
    marks = {t.id: classify_boundary(t, limit=suite.config.policy_threshold) for t in tests}
    behaviors = [inject_boundary_atoms(b, marks[t.id]) for t, b in zip(tests, behaviors, strict=True)]
    for t, b in zip(tests, behaviors, strict=True):
        t.behavior = b
    return simulate_removal(
        tests,
        behaviors,
        test_id,
        declared_critical=declared,
        policies=suite.config.policies,
    )
