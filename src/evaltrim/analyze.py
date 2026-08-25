"""End-to-end analysis pipeline."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evaltrim.behavior import extract_behavior
from evaltrim.boundary import classify_boundary, inject_boundary_atoms, unique_boundary_ids
from evaltrim.cache import cache_enabled, load_cached_analysis, store_cached_analysis, suite_fingerprint
from evaltrim.candidates import CandidatePairGenerator
from evaltrim.coverage import compute_coverage, covers_declared, unique_atoms_by_test
from evaltrim.embeddings import load_encoder
from evaltrim.errors import TestNotFoundError
from evaltrim.incremental import PairScoreCache
from evaltrim.intelligence.boundaries import missing_boundary_candidates
from evaltrim.intelligence.clusters import cluster_behaviors
from evaltrim.intelligence.compression import compression_stats
from evaltrim.intelligence.conflicts import evaluator_conflict_graph
from evaltrim.intelligence.evidence import ledger_for
from evaltrim.intelligence.failure_value import failure_detection_value
from evaltrim.intelligence.graph import behavior_graph
from evaltrim.intelligence.infogain import information_gain as compute_information_gain
from evaltrim.intelligence.witness import classify_witness, unique_signatures
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
from evaltrim.scoring import value_components, value_score
from evaltrim.similarity import SimilarityEngine
from evaltrim.simulate import RemovalIndex, RemovalSimulation, simulate_cached, simulate_removal


def _pair_fields(raw: dict[str, Any]) -> tuple[float, float, float, float, float, list[str], list[str], list[str]]:
    return (
        float(raw["score"]),
        float(raw["semantic"]),
        float(raw["behavior_overlap"]),
        float(raw["expected_similarity"]),
        float(raw["historical_overlap"]),
        [str(x) for x in raw["shared"]],
        [str(x) for x in raw["unique_left"]],
        [str(x) for x in raw["unique_right"]],
    )


METHODOLOGY = (
    "Scores are heuristics, not statistical guarantees. Semantic similarity is three-tier: "
    "cheap lexical (tier 1), local hashing representation (tier 2), optional encoder/LLM (tier 3). "
    "Embeddings and semantic retrieval may CREATE CANDIDATES; they never independently authorize RETIRE. "
    "Redundancy also uses Jaccard overlap of behavior atoms, expected-oracle similarity, and historical "
    "failure-rate closeness. Candidate generation uses full pairwise comparison below "
    "config.full_pairwise_limit and layered blocking (exact hash, lexical prefix, behavior, inverted-index, "
    "optional embeddings) above it. Unique witnesses include singleton atoms, condition combinations, "
    "boundaries, unique requirements, and unique failure families. "
    "Removal is simulated in memory and never deletes files. KEEP always wins over RETIRE when "
    "a test is the only witness for a critical behavior. A high semantic score alone never retires. "
    "Counterfactual results are reused across equivalent coverage signatures; safety math is unchanged."
)


def analyze_suite(
    suite: TestSuite,
    *,
    extractor: BehaviorExtractor | None = None,
    pair_limit: int | None = None,
    use_cache: bool = True,
) -> AnalysisResult:
    if use_cache and pair_limit is None:
        cached = load_cached_analysis(suite)
        if cached is not None:
            cached.timings = {**dict(cached.timings), "cache_hit": 1.0}
            return cached
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
    signature_unique = unique_signatures(tests, behaviors)
    combo_unique = {tid for tid, key in signature_unique.items() if len(key[2]) >= 2}
    failure_unique = _unique_failures(tests)
    family_unique = _unique_failure_families(tests)
    req_unique = _unique_requirements(suite)

    t_cand = perf_counter()
    generator = CandidatePairGenerator(
        full_pairwise_limit=cfg.full_pairwise_limit,
        neighbor_k=cfg.candidate_neighbor_k,
    )
    index_pairs = generator.pairs(tests, behaviors, encoder=encoder)
    candidate_s = perf_counter() - t_cand

    pairs: list[RedundantPair] = []
    max_redundancy: dict[str, float] = {t.id: 0.0 for t in tests}
    partners: dict[str, list[str]] = defaultdict(list)
    semantic_triples: list[tuple[str, str, float, float]] = []

    t_sim = perf_counter()
    pair_cache = PairScoreCache.load(suite) if pair_limit is None else None
    for i, j in index_pairs:
        pair_hit = pair_cache.get(tests[i], tests[j]) if pair_cache else None
        if pair_hit is None:
            scored = engine.pair_score(tests[i].id, tests[j].id)
            raw: dict[str, Any] = {
                "score": scored["score"],
                "semantic": scored["semantic"],
                "behavior_overlap": scored["behavior_overlap"],
                "expected_similarity": scored["expected_similarity"],
                "historical_overlap": scored["historical_overlap"],
                "shared": list(scored["shared"]),
                "unique_left": list(scored["unique_left"]),
                "unique_right": list(scored["unique_right"]),
            }
            if pair_cache is not None:
                pair_cache.put(tests[i], tests[j], raw)
        else:
            raw = pair_hit
        score, semantic, overlap, expected, historical, shared, unique_left, unique_right = _pair_fields(raw)
        max_redundancy[tests[i].id] = max(max_redundancy[tests[i].id], score)
        max_redundancy[tests[j].id] = max(max_redundancy[tests[j].id], score)
        semantic_triples.append((tests[i].id, tests[j].id, semantic, expected))
        decision = _decision(
            score=score,
            semantic=semantic,
            overlap=overlap,
            expected=expected,
            historical=historical,
            unique_left=unique_left,
            unique_right=unique_right,
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
                    behavior_overlap=overlap,
                    expected_similarity=expected,
                    historical_overlap=historical,
                    shared=shared,
                    unique_left=unique_left,
                    unique_right=unique_right,
                    recommendation=decision.recommendation,
                    rationale=decision.reasons[0] if decision.reasons else decision.label,
                    decision=decision,
                )
            )
    similarity_s = perf_counter() - t_sim
    pair_hits = float(pair_cache.hits) if pair_cache else 0.0
    pair_misses = float(pair_cache.misses) if pair_cache else float(len(index_pairs))
    if pair_cache is not None:
        pair_cache.save(suite)
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
    tests_by_id = {t.id: t for t in tests}
    exact_input_conflict_ids: set[str] = set()
    for item in oracle_conflicts:
        left = tests_by_id.get(item.left_id)
        right = tests_by_id.get(item.right_id)
        if left is None or right is None:
            continue
        if left.input.strip() == right.input.strip():
            exact_input_conflict_ids.add(left.id)
            exact_input_conflict_ids.add(right.id)
    health_by_id = {h.test_id: h for h in oracle_health}
    max_cost = max(((t.run_stats.estimated_cost_usd or 0.0) if t.run_stats else 0.0) for t in tests) or 1.0

    t_rem = perf_counter()
    rem_index = RemovalIndex.build(
        tests,
        behaviors,
        declared_critical=declared,
        baseline=coverage,
        policies=policies,
        unique=unique,
        suite=suite,
    )
    merge_ids = {p.left_id for p in pairs if p.recommendation == RecommendationState.MERGE} | {
        p.right_id for p in pairs if p.recommendation == RecommendationState.MERGE
    }
    max_pair_sem: dict[str, float] = {t.id: 0.0 for t in tests}
    max_pair_ov: dict[str, float] = {t.id: 0.0 for t in tests}
    for pair in pairs:
        max_pair_sem[pair.left_id] = max(max_pair_sem[pair.left_id], pair.semantic)
        max_pair_sem[pair.right_id] = max(max_pair_sem[pair.right_id], pair.semantic)
        max_pair_ov[pair.left_id] = max(max_pair_ov[pair.left_id], pair.behavior_overlap)
        max_pair_ov[pair.right_id] = max(max_pair_ov[pair.right_id], pair.behavior_overlap)
    evidence: list[TestEvidence] = []
    recommendations = []
    witnesses: list[WitnessRecord] = []
    sim_cache: dict[tuple[object, ...], RemovalSimulation] = {}
    simulations_run = 0
    for test, behavior in zip(tests, behaviors, strict=True):
        before = len(sim_cache)
        sim = simulate_cached(rem_index, test.id, sim_cache)
        if len(sim_cache) > before:
            simulations_run += 1
        uniq = unique.get(test.id, [])
        uniq_crit = _unique_critical_indexed(rem_index, test.id, behavior, uniq)
        if test.id in req_unique:
            uniq_crit = sorted(set(uniq_crit) | {f"requirement:{r}" for r in req_unique[test.id]})
        components = value_components(
            test,
            behavior,
            unique_atoms=uniq,
            total_atoms=len(universe),
            max_cost=max_cost,
            weights=cfg.value_weights,
            requirement_n=len(test.requirement_ids),
        )
        score = value_score(
            test,
            behavior,
            unique_atoms=uniq,
            total_atoms=len(universe),
            max_cost=max_cost,
            weights=cfg.value_weights,
            requirement_n=len(test.requirement_ids),
        )
        low_conf = behavior.confidence < 0.5 or (behavior.source == "heuristic" and behavior.domain == "unknown")
        life = infer_lifecycle(test, conflict=test.id in conflict_ids, stale_days=cfg.stale_days)
        classified = classify_witness(
            test=test,
            behavior=behavior,
            unique_atoms=uniq,
            unique_critical=uniq_crit,
            unique_boundary=test.id in boundary_unique,
            unique_requirement=req_unique.get(test.id, []),
            unique_failure=test.id in failure_unique,
            unique_failure_family=test.id in family_unique,
            unique_signature=test.id in signature_unique,
            simulation=sim,
            conflict=test.id in conflict_ids,
            exact_input_conflict=test.id in exact_input_conflict_ids,
        )
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
            unique_failure=test.id in failure_unique,
            unique_failure_family=test.id in family_unique,
            unique_requirement=req_unique.get(test.id, []),
            oracle_status=(health_by_id[test.id].status if test.id in health_by_id else OracleStatus.TRUSTED),
            lifecycle=life,
            policies=policies,
            merge_candidate=test.id in merge_ids,
        )
        rec.pair_ids = partners.get(test.id, [])
        rec.evidence = ledger_for(
            rec,
            test=test,
            simulation=sim,
            semantic=max_pair_sem[test.id],
            overlap=max_pair_ov[test.id],
            oracle_status=(health_by_id[test.id].status if test.id in health_by_id else None),
        )
        recommendations.append(rec)
        evidence.append(
            TestEvidence(
                test_id=test.id,
                behavior=behavior,
                unique_atoms=uniq,
                shared_atoms=sorted(set(behavior.atoms()) - set(uniq)),
                recommendation=rec,
                value_score=score,
                is_critical_witness=classified["is_critical_witness"],
                redundancy_max=round(max_redundancy[test.id], 6),
                stale=test.is_stale(stale_days=cfg.stale_days),
                conflict=test.id in conflict_ids,
                lifecycle=life.value,
                stale_status=stale_status(test, stale_days=cfg.stale_days).value,
                value_components=components,
            )
        )
        extra = []
        if test.id in combo_unique:
            extra.append("unique condition combination")
        if test.id in failure_unique:
            extra.append("unique failure history")
        if classified["is_unique_witness"]:
            witness_summary = "Unique coverage witness: " + ", ".join(classified["kinds"][:4] or ["counterfactual"])
            if uniq:
                witness_summary += " | " + ", ".join(_pretty(a) for a in uniq[:6])
        elif uniq:
            witness_summary = "Distinctive atoms (anti-merge, not a coverage witness): " + ", ".join(
                _pretty(a) for a in uniq[:6]
            )
        else:
            witness_summary = "No unique behavior atom; overlapping coverage."
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
                unique_requirement=req_unique.get(test.id, []),
                unique_failure_family=test.id in family_unique,
                unique_boundary=test.id in boundary_unique,
                is_unique_witness=classified["is_unique_witness"],
                is_critical_witness=classified["is_critical_witness"],
                witness_confidence=classified["witness_confidence"],
                witness_kinds=classified["kinds"],
                witness_evidence=classified["evidence"],
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
    analysis = AnalysisResult(
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
            "pair_cache_hits": pair_hits,
            "pair_cache_misses": pair_misses,
            "simulations_executed": float(simulations_run),
            "simulation_cache_entries": float(len(sim_cache)),
        },
        candidate_pairs_considered=len(index_pairs),
        embeddings_used=encoder is not None,
        llm_used=extractor is not None or cfg.llm_enabled,
    )
    analysis.evaluator_conflicts = evaluator_conflict_graph(analysis)
    analysis.missing_boundaries = missing_boundary_candidates(suite)
    analysis.behavior_graph = behavior_graph(suite, analysis)
    analysis.compression = compression_stats(analysis)
    analysis.clusters = cluster_behaviors(suite, analysis)["clusters"]
    analysis.information_gain = compute_information_gain(suite, analysis)
    analysis.failure_values = failure_detection_value(suite, analysis)
    gain_by = {row["test_id"]: row["information_gain"] for row in analysis.information_gain}
    fail_by = {row["test_id"]: row["failure_detection_value"] for row in analysis.failure_values}
    for rec in analysis.recommendations:
        if rec.evidence:
            rec.evidence.information_gain = gain_by.get(rec.test_id)
            rec.evidence.failure_detection_value = fail_by.get(rec.test_id)
    if use_cache and pair_limit is None:
        store_cached_analysis(suite, analysis)
        try:
            if cache_enabled():
                from evaltrim.store import append_history

                append_history(
                    "analysis",
                    {
                        "name": suite.name,
                        "keep": keep,
                        "merge": merge,
                        "retire": retire,
                        "review": review,
                        "critical_coverage": analysis.coverage.critical_coverage,
                    },
                    suite_hash=suite_fingerprint(suite),
                )
        except Exception:  # noqa: BLE001
            pass
    return analysis


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
        "ADD_CANDIDATE items are suggestions only.",
    ]
    actions = [
        {
            "test_id": r.test_id,
            "action": r.state.value,
            "reasons": r.reasons,
            "evidence": r.evidence.model_dump() if r.evidence else None,
        }
        for r in result.recommendations
    ]
    return MaintenanceReport(
        generated_at=datetime.now(UTC),
        summary=result.summary,
        coverage=result.coverage,
        candidate_merges=merges,
        candidate_retirements=retirements,
        stale_cases=stale,
        unique_witnesses=[w for w in result.witnesses if w.is_unique_witness],
        critical_coverage=result.coverage.critical_coverage,
        estimated_suite_reduction=result.summary.estimated_ci_reduction,
        evidence=result.evidence,
        notes=notes,
        requirement_coverage=result.requirement_coverage,
        add_candidates=list(result.missing_boundaries),
        actions=actions,
    )


def _requirement_coverage(suite: TestSuite) -> list[RequirementCoverage]:
    rows: list[RequirementCoverage] = []
    for req in suite.requirements:
        holders = [t.id for t in suite.tests if req.id in t.requirement_ids]
        uncovered = len(holders) == 0
        if uncovered and req.critical:
            status = "critical_uncovered"
        elif uncovered:
            status = "uncovered"
        elif req.critical and not any(suite.get(tid).tags.critical for tid in holders):
            status = "partially_covered"
        else:
            status = "covered"
        rows.append(
            RequirementCoverage(
                requirement_id=req.id,
                description=req.description,
                critical=req.critical,
                covered_by=holders,
                uncovered=uncovered,
                status=status,
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
    env = {"timeout", "provider_error", "rate_limit", "http_5xx", "infrastructure", "network"}
    real: list[str] = []
    for test in tests:
        stats = test.run_stats
        if not stats or stats.failures <= 0:
            continue
        outcomes = [str(o).lower() for o in (stats.outcomes or [])]
        if outcomes:
            fails = [o for o in outcomes if o not in {"pass", "passed", "ok"}]
            if fails and all(o in env for o in fails):
                continue
        real.append(test.id)
    return set(real) if len(real) == 1 else set()


def _unique_failure_families(tests) -> set[str]:
    index: dict[str, list[str]] = defaultdict(list)
    for test in tests:
        if test.failure_family:
            index[test.failure_family].append(test.id)
    return {ids[0] for ids in index.values() if len(ids) == 1}


def _unique_requirements(suite: TestSuite) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for req in suite.requirements:
        holders = [t.id for t in suite.tests if req.id in t.requirement_ids]
        if len(holders) == 1:
            mapping[holders[0]].append(req.id)
    return dict(mapping)


def _unique_critical_indexed(index: RemovalIndex, test_id: str, behavior, unique_atoms: list[str]) -> list[str]:
    declared_norm = {d.lower().replace(" ", "_") for d in index.declared}
    hits = []
    for name, holders in index.critical_holders.items():
        if len(holders) == 1 and test_id in holders:
            hits.append(name.lower().replace(" ", "_"))
    if behavior.critical and index.critical_test_ids == {test_id}:
        hits.append("critical")
    for atom in unique_atoms:
        name = atom.split(":", 1)[-1]
        if name in declared_norm and name not in hits:
            hits.append(atom)
    return hits


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
    if boundary and (boundary_l != boundary_r or meaningful_l or meaningful_r):
        state = RecommendationState.KEEP
        reasons.append("Boundary uniqueness: do not collapse threshold neighbors.")
        confidence = 0.95
        label = "BOUNDARY_KEEP"
    elif unique or (critical and (meaningful_l or meaningful_r)):
        state = RecommendationState.KEEP
        reasons.append("Unique behavior remains on at least one side.")
        confidence = 0.9
        label = "KEEP_BOTH"
    elif conflict:
        state = RecommendationState.REVIEW
        reasons.append("Oracle conflict: similar inputs, dissimilar expected.")
        confidence = 0.55
        label = "ORACLE_CONFLICT"
    elif overlap >= 0.99 and expected >= 0.8 and not unique and (score >= merge_threshold or semantic >= 0.80):
        state = RecommendationState.MERGE
        reasons.append("REDUNDANT_CANDIDATE: high overlap on semantics, behavior, and expected; no unique atom.")
        confidence = min(0.93, 0.5 + 0.5 * max(score, semantic))
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
        suite=suite,
    )
