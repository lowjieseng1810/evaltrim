"""Canonical internal models. Importers should map into these types."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecommendationState(str, Enum):
    KEEP = "KEEP"
    MERGE = "MERGE"
    RETIRE = "RETIRE"
    REVIEW = "REVIEW"
    ADD_CANDIDATE = "ADD_CANDIDATE"


class Verdict(str, Enum):
    SAFE_TO_RETIRE = "SAFE_TO_RETIRE"
    KEEP = "KEEP"
    REVIEW = "REVIEW"
    UNCERTAIN = "UNCERTAIN"


class FlakeStatus(str, Enum):
    STABLE = "STABLE"
    FLAKY = "FLAKY"
    DEGRADED = "DEGRADED"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    QUARANTINED = "QUARANTINED"


class RegressionClass(str, Enum):
    UNCHANGED = "UNCHANGED"
    EXPECTED_CHANGE = "EXPECTED_CHANGE"
    POSSIBLE_REGRESSION = "POSSIBLE_REGRESSION"
    CONFIRMED_REGRESSION = "CONFIRMED_REGRESSION"
    UNCERTAIN = "UNCERTAIN"


class DriftSource(str, Enum):
    CODE_CHANGE = "code_change"
    PROMPT_CHANGE = "prompt_change"
    CONFIGURATION_CHANGE = "configuration_change"
    TOOL_SCHEMA_CHANGE = "tool_schema_change"
    MODEL_PROVIDER_CHANGE = "model_provider_change"
    TEST_ORACLE_CHANGE = "test_oracle_change"
    ENVIRONMENT_CHANGE = "environment_change"
    UNCERTAIN = "uncertain"


class LikelySource(str, Enum):
    """Heuristic attribution. Not causal proof."""

    CODE = "CODE"
    PROMPT = "PROMPT"
    CONFIG = "CONFIG"
    TOOL = "TOOL"
    MODEL = "MODEL"
    PROVIDER = "PROVIDER"
    ORACLE = "ORACLE"
    ENVIRONMENT = "ENVIRONMENT"
    UNKNOWN = "UNKNOWN"


class ImpactPriority(str, Enum):
    CRITICAL = "CRITICAL"
    DIRECT = "DIRECT"
    ADJACENT = "ADJACENT"
    RISKY = "RISKY"
    LOW_PRIORITY = "LOW_PRIORITY"


class OracleStatus(str, Enum):
    TRUSTED = "TRUSTED"
    REVIEW = "REVIEW"
    CONFLICT = "CONFLICT"
    STALE = "STALE"


class SafetyPolicies(BaseModel):
    """Optional policy-as-code. Conservative defaults."""

    model_config = ConfigDict(extra="forbid")

    minimum_critical_coverage: float = 1.0
    max_behavior_coverage_drop: float = 0.01
    minimum_retirement_confidence: float = 0.80
    fail_on_oracle_conflict: bool = True
    critical_behavior_loss: str = "fail"

    @model_validator(mode="after")
    def _safe_ranges(self) -> SafetyPolicies:
        if not 0.0 <= self.minimum_critical_coverage <= 1.0:
            raise ValueError("minimum_critical_coverage must be in [0, 1]")
        if not 0.0 <= self.max_behavior_coverage_drop <= 1.0:
            raise ValueError("max_behavior_coverage_drop must be in [0, 1]")
        if not 0.0 <= self.minimum_retirement_confidence <= 1.0:
            raise ValueError("minimum_retirement_confidence must be in [0, 1]")
        if self.minimum_retirement_confidence < 0.5:
            raise ValueError(
                "unsafe retirement setting: minimum_retirement_confidence < 0.5 would allow low-confidence RETIRE"
            )
        if self.critical_behavior_loss not in {"fail", "warn"}:
            raise ValueError("critical_behavior_loss must be 'fail' or 'warn'")
        return self


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str = ""
    critical: bool = False


class RunStats(BaseModel):
    """Optional historical execution statistics. Never required."""

    model_config = ConfigDict(extra="forbid")

    runs: int = 0
    passes: int = 0
    failures: int = 0
    last_run: datetime | None = None
    average_latency_ms: float | None = None
    estimated_cost_usd: float | None = None
    outcomes: list[str] = Field(default_factory=list)

    @property
    def failure_rate(self) -> float | None:
        if self.runs <= 0:
            return None
        return self.failures / self.runs


class Tags(BaseModel):
    """Flexible tags. Known fields are first-class; extras are preserved."""

    model_config = ConfigDict(extra="allow")

    domain: str | None = None
    action: str | None = None
    behavior: list[str] = Field(default_factory=list)
    state: str | None = None
    critical: bool = False
    conditions: list[str] = Field(default_factory=list)


class Behavior(BaseModel):
    """Normalized behavioral signature for a single test."""

    model_config = ConfigDict(extra="forbid")

    domain: str = "unknown"
    action: str = "unknown"
    conditions: list[str] = Field(default_factory=list)
    state: str = "normal"
    critical: bool = False
    source: str = "tags"
    confidence: float = 1.0

    @field_validator("conditions")
    @classmethod
    def _dedupe_conditions(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            key = item.strip().lower().replace(" ", "_")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def atoms(self) -> list[str]:
        """Atomic coverage keys used for uniqueness and coverage math."""
        items = [f"domain:{self.domain}", f"action:{self.action}", f"state:{self.state}"]
        items.extend(f"condition:{c}" for c in self.conditions)
        if self.critical:
            items.append("flag:critical")
        return items

    def label(self) -> str:
        cond = ", ".join(self.conditions) if self.conditions else "none"
        return f"domain={self.domain} action={self.action} condition={cond} state={self.state} critical={self.critical}"


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    input: str
    expected: str
    tags: Tags = Field(default_factory=Tags)
    metadata: dict[str, Any] = Field(default_factory=dict)
    run_stats: RunStats | None = None
    behavior: Behavior | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    provenance_files: list[str] = Field(default_factory=list)
    tool_dependencies: list[str] = Field(default_factory=list)
    failure_family: str | None = None
    quarantined: bool = False

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("test id must be a non-empty string")
        return value.strip()

    @property
    def source(self) -> str | None:
        raw = self.metadata.get("source")
        return str(raw) if raw is not None else None

    @property
    def created_at(self) -> str | None:
        raw = self.metadata.get("created_at")
        return str(raw) if raw is not None else None

    def is_stale(self, *, stale_days: int = 180) -> bool:
        if self.metadata.get("stale") is True:
            return True
        last = self.run_stats.last_run if self.run_stats else None
        if last is None:
            created = self.created_at
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    age_days = (datetime.now(dt.tzinfo) - dt).days
                    return age_days >= stale_days and (not self.run_stats or (self.run_stats.failures == 0))
                except ValueError:
                    return False
            return False
        age_days = (datetime.now(last.tzinfo) - last).days
        return age_days >= stale_days and (self.run_stats is None or self.run_stats.failures == 0)


class RedundancyWeights(BaseModel):
    semantic: float = 0.35
    behavior: float = 0.30
    expected: float = 0.20
    historical: float = 0.15

    @model_validator(mode="after")
    def _sum_to_one(self) -> RedundancyWeights:
        total = self.semantic + self.behavior + self.expected + self.historical
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"redundancy weights must sum to 1.0, got {total}")
        return self


class ValueWeights(BaseModel):
    """Visible, user-overridable components of the heuristic value score. Must sum to 1.0."""

    uniqueness: float = 0.18
    criticality: float = 0.18
    information_gain: float = 0.12
    historical_failures: float = 0.12
    requirement_coverage: float = 0.10
    boundary: float = 0.10
    inverse_cost: float = 0.08
    inverse_flakiness: float = 0.07
    oracle_confidence: float = 0.05

    @model_validator(mode="after")
    def _sum_to_one(self) -> ValueWeights:
        total = (
            self.uniqueness
            + self.criticality
            + self.information_gain
            + self.historical_failures
            + self.requirement_coverage
            + self.boundary
            + self.inverse_cost
            + self.inverse_flakiness
            + self.oracle_confidence
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"value weights must sum to 1.0, got {total}")
        return self


class AnalysisConfig(BaseModel):
    weights: RedundancyWeights = Field(default_factory=RedundancyWeights)
    value_weights: ValueWeights = Field(default_factory=ValueWeights)
    redundancy_threshold: float = 0.80
    merge_threshold: float = 0.90
    stale_days: int = 180
    aging_days: int = 90
    llm_enabled: bool = False
    llm_provider: str | None = None
    embeddings_enabled: bool = False
    persist_embedding_cache: bool = False
    candidate_neighbor_k: int = 40
    full_pairwise_limit: int = 200
    policy_threshold: float = 500.0
    policies: SafetyPolicies = Field(default_factory=SafetyPolicies)

    @model_validator(mode="after")
    def _threshold_ranges(self) -> AnalysisConfig:
        for name in ("redundancy_threshold", "merge_threshold"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.merge_threshold < self.redundancy_threshold:
            raise ValueError("merge_threshold must be >= redundancy_threshold")
        if self.stale_days < 1 or self.aging_days < 1:
            raise ValueError("stale_days and aging_days must be >= 1")
        if self.candidate_neighbor_k < 1 or self.full_pairwise_limit < 1:
            raise ValueError("candidate_neighbor_k and full_pairwise_limit must be >= 1")
        return self


class TestSuite(BaseModel):
    """Canonical suite document (YAML/JSON)."""

    model_config = ConfigDict(extra="ignore")

    tests: list[TestCase]
    critical_behaviors: list[str] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)
    name: str | None = None
    description: str | None = None

    @field_validator("tests")
    @classmethod
    def _unique_ids(cls, tests: list[TestCase]) -> list[TestCase]:
        if not tests:
            raise ValueError("suite must contain at least one test")
        seen: set[str] = set()
        for test in tests:
            if test.id in seen:
                raise ValueError(f"duplicate test id: {test.id}")
            seen.add(test.id)
        return tests

    def get(self, test_id: str) -> TestCase:
        for test in self.tests:
            if test.id == test_id:
                return test
        raise KeyError(test_id)


class SuiteSummary(BaseModel):
    name: str | None = None
    test_count: int
    critical_test_count: int
    declared_critical_behaviors: list[str]
    keep: int = 0
    merge: int = 0
    retire: int = 0
    review: int = 0
    estimated_ci_reduction: float = 0.0


class CoverageResult(BaseModel):
    behavior_atoms: int
    covered_atoms: int
    behavior_coverage: float
    critical_atoms: int
    covered_critical_atoms: int
    critical_coverage: float
    uncovered_critical: list[str] = Field(default_factory=list)
    uncovered_behaviors: list[str] = Field(default_factory=list)
    critical_by_name: dict[str, bool] = Field(default_factory=dict)

    def as_percent(self, field: str) -> str:
        value = getattr(self, field)
        return f"{value * 100:.1f}%"


class RedundancyDecision(BaseModel):
    label: str
    semantic_similarity: float
    behavior_overlap: float
    expected_behavior_similarity: float
    historical_overlap: float
    unique_behavior: list[str] = Field(default_factory=list)
    critical_behavior: bool = False
    boundary_unique: bool = False
    conflict: bool = False
    decision_confidence: float
    recommendation: RecommendationState
    reasons: list[str] = Field(default_factory=list)


class RedundantPair(BaseModel):
    left_id: str
    right_id: str
    score: float
    semantic: float
    behavior_overlap: float
    expected_similarity: float
    historical_overlap: float
    shared: list[str]
    unique_left: list[str]
    unique_right: list[str]
    recommendation: RecommendationState
    rationale: str
    decision: RedundancyDecision | None = None


class WitnessRecord(BaseModel):
    test_id: str
    unique_atoms: list[str]
    unique_critical: list[str]
    summary: str
    recommendation: RecommendationState
    boundary_marks: list[str] = Field(default_factory=list)
    unique_combo: bool = False
    unique_failure: bool = False
    unique_requirement: list[str] = Field(default_factory=list)
    unique_failure_family: bool = False
    unique_boundary: bool = False


class EvidenceLedger(BaseModel):
    """Serializable explanation for a recommendation. Not a causal proof."""

    decision: str
    semantic_similarity: float | None = None
    behavior_overlap: float | None = None
    unique_witnesses_lost: int = 0
    critical_coverage_lost: float = 0.0
    requirement_coverage_lost: int = 0
    historical_failure_contribution: float = 0.0
    counterfactual_coverage_loss: float = 0.0
    counterfactual_status: str | None = None
    oracle_status: str | None = None
    notes: list[str] = Field(default_factory=list)
    proof: list[dict[str, Any]] = Field(default_factory=list)
    information_gain: float | None = None
    failure_detection_value: float | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Recommendation(BaseModel):
    test_id: str
    state: RecommendationState
    reasons: list[str]
    value_score: float
    confidence: float
    pair_ids: list[str] = Field(default_factory=list)
    evidence: EvidenceLedger | None = None


class TestEvidence(BaseModel):
    test_id: str
    behavior: Behavior
    unique_atoms: list[str]
    shared_atoms: list[str]
    recommendation: Recommendation
    value_score: float
    is_critical_witness: bool
    redundancy_max: float
    stale: bool
    conflict: bool
    lifecycle: str = "ACTIVE"
    stale_status: str = "ACTIVE"
    value_components: dict[str, float] = Field(default_factory=dict)


class RemovalSimulation(BaseModel):
    test_id: str
    before_tests: int
    after_tests: int
    before_coverage: CoverageResult
    after_coverage: CoverageResult
    lost_atoms: list[str]
    lost_critical_atoms: list[str]
    lost_unique_witnesses: list[str]
    unique_witnesses_before: int = 0
    unique_witnesses_after: int = 0
    critical_by_name_before: dict[str, bool] = Field(default_factory=dict)
    critical_by_name_after: dict[str, bool] = Field(default_factory=dict)
    lost_requirement_ids: list[str] = Field(default_factory=list)
    historical_failure_contribution: float = 0.0
    counterfactual_coverage_loss: float = 0.0
    verdict: Verdict
    reasons: list[str]
    evidence: dict[str, Any] = Field(default_factory=dict)


class OracleConflict(BaseModel):
    left_id: str
    right_id: str
    kind: str
    detail: str


class OracleHealth(BaseModel):
    test_id: str
    status: OracleStatus
    confidence: float
    reasons: list[str] = Field(default_factory=list)


class RequirementCoverage(BaseModel):
    requirement_id: str
    description: str = ""
    critical: bool = False
    covered_by: list[str] = Field(default_factory=list)
    uncovered: bool = False
    status: str = "uncovered"


class AnalysisResult(BaseModel):
    summary: SuiteSummary
    coverage: CoverageResult
    evidence: list[TestEvidence]
    pairs: list[RedundantPair]
    witnesses: list[WitnessRecord]
    recommendations: list[Recommendation]
    conflicts: list[str] = Field(default_factory=list)
    methodology: str = ""
    oracle_health: list[OracleHealth] = Field(default_factory=list)
    oracle_conflicts: list[OracleConflict] = Field(default_factory=list)
    requirement_coverage: list[RequirementCoverage] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)
    candidate_pairs_considered: int = 0
    embeddings_used: bool = False
    llm_used: bool = False
    behavior_graph: dict[str, Any] = Field(default_factory=dict)
    compression: dict[str, Any] = Field(default_factory=dict)
    evaluator_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    missing_boundaries: list[dict[str, Any]] = Field(default_factory=list)
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    information_gain: list[dict[str, Any]] = Field(default_factory=list)
    failure_values: list[dict[str, Any]] = Field(default_factory=list)
    contract_version: str = "1.0"


class MaintenanceReport(BaseModel):
    generated_at: datetime
    summary: SuiteSummary
    coverage: CoverageResult
    candidate_merges: list[RedundantPair]
    candidate_retirements: list[Recommendation]
    stale_cases: list[str]
    unique_witnesses: list[WitnessRecord]
    critical_coverage: float
    estimated_suite_reduction: float
    evidence: list[TestEvidence]
    notes: list[str] = Field(default_factory=list)
    requirement_coverage: list[RequirementCoverage] = Field(default_factory=list)
    add_candidates: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
