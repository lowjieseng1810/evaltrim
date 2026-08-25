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


class Verdict(str, Enum):
    SAFE_TO_RETIRE = "SAFE_TO_RETIRE"
    KEEP = "KEEP"
    REVIEW = "REVIEW"


class RunStats(BaseModel):
    """Optional historical execution statistics. Never required."""

    model_config = ConfigDict(extra="forbid")

    runs: int = 0
    passes: int = 0
    failures: int = 0
    last_run: datetime | None = None
    average_latency_ms: float | None = None
    estimated_cost_usd: float | None = None

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
        return (
            f"domain={self.domain} action={self.action} "
            f"condition={cond} state={self.state} critical={self.critical}"
        )


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    input: str
    expected: str
    tags: Tags = Field(default_factory=Tags)
    metadata: dict[str, Any] = Field(default_factory=dict)
    run_stats: RunStats | None = None
    behavior: Behavior | None = None

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
                    return age_days >= stale_days and (
                        not self.run_stats or (self.run_stats.failures == 0)
                    )
                except ValueError:
                    return False
            return False
        age_days = (datetime.now(last.tzinfo) - last).days
        return age_days >= stale_days and (self.run_stats.failures or 0) == 0


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


class AnalysisConfig(BaseModel):
    weights: RedundancyWeights = Field(default_factory=RedundancyWeights)
    redundancy_threshold: float = 0.80
    merge_threshold: float = 0.90
    stale_days: int = 180
    llm_enabled: bool = False
    llm_provider: str | None = None


class TestSuite(BaseModel):
    """Canonical suite document (YAML/JSON)."""

    model_config = ConfigDict(extra="ignore")

    tests: list[TestCase]
    critical_behaviors: list[str] = Field(default_factory=list)
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

    def as_percent(self, field: str) -> str:
        value = getattr(self, field)
        return f"{value * 100:.1f}%"


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


class WitnessRecord(BaseModel):
    test_id: str
    unique_atoms: list[str]
    unique_critical: list[str]
    summary: str
    recommendation: RecommendationState


class Recommendation(BaseModel):
    test_id: str
    state: RecommendationState
    reasons: list[str]
    value_score: float
    confidence: float
    pair_ids: list[str] = Field(default_factory=list)


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


class RemovalSimulation(BaseModel):
    test_id: str
    before_tests: int
    after_tests: int
    before_coverage: CoverageResult
    after_coverage: CoverageResult
    lost_atoms: list[str]
    lost_critical_atoms: list[str]
    lost_unique_witnesses: list[str]
    verdict: Verdict
    reasons: list[str]


class AnalysisResult(BaseModel):
    summary: SuiteSummary
    coverage: CoverageResult
    evidence: list[TestEvidence]
    pairs: list[RedundantPair]
    witnesses: list[WitnessRecord]
    recommendations: list[Recommendation]
    conflicts: list[str] = Field(default_factory=list)
    methodology: str = ""


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
