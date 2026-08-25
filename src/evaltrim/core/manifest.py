"""Canonical evaluation records. Vendor-neutral; importers map into these types."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evaltrim.models import Behavior


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Any = None
    latency_ms: float | None = None
    error: str | None = None


class TrajectoryStep(BaseModel):
    kind: str
    name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str | None = None
    created_at: str | None = None
    imported_from: str | None = None
    recording_id: str | None = None
    model: str | None = None
    provider: str | None = None


class Usage(BaseModel):
    latency_ms: float | None = None
    ttft_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class GraderSpec(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


class GradeResult(BaseModel):
    grader: str
    passed: bool | None
    score: float | None = None
    detail: str = ""
    skipped: bool = False


class AgentOutput(BaseModel):
    text: str = ""
    messages: list[Message] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    trajectory: list[TrajectoryStep] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    model: str | None = None
    provider: str | None = None


class EvaluationRecord(BaseModel):
    """Stable internal evaluation unit. Suite tests map 1:1 onto this shape."""

    model_config = ConfigDict(extra="allow")

    id: str
    version: str = "1"
    agent: str | None = None
    input: str
    messages: list[Message] = Field(default_factory=list)
    expected: str | None = None
    requirements: list[str] = Field(default_factory=list)
    behavior: Behavior | None = None
    critical: bool = False
    graders: list[GraderSpec] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)
    output: AgentOutput | None = None
    grades: list[GradeResult] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    lifecycle: str = "ACTIVE"
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_test_case(cls, test: Any, *, agent: str | None = None) -> EvaluationRecord:
        from evaltrim.models import TestCase

        if not isinstance(test, TestCase):
            raise TypeError("from_test_case expects TestCase")
        graders = [GraderSpec(type="contains")] if test.expected else []
        return cls(
            id=test.id,
            agent=agent,
            input=test.input,
            expected=test.expected,
            requirements=list(test.requirement_ids),
            behavior=test.behavior,
            critical=bool(test.tags.critical),
            graders=graders,
            provenance=Provenance(source=test.source, created_at=test.created_at),
            metadata=dict(test.metadata),
        )
