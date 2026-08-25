"""Normalized trace model and JSON/JSONL ingestion."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evaltrim.errors import SuiteValidationError


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: int = 0
    completion: int = 0
    total: int = 0


class TraceEvent(BaseModel):
    """Stable internal event schema for sessions, turns, model/tool calls, and outputs."""

    model_config = ConfigDict(extra="ignore")

    kind: str
    timestamp: datetime | None = None
    session_id: str | None = None
    turn: int | None = None
    trajectory_position: int = 0
    model: str | None = None
    provider: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float | None = None
    latency_ms: float | None = None
    tool: str | None = None
    tool_arguments: dict[str, Any] | None = None
    result: Any = None
    output: str | None = None
    provenance: str | None = None
    state_from: str | None = None
    state_to: str | None = None


class NormalizedTrace(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str
    events: list[TraceEvent] = Field(default_factory=list)
    provenance: str | None = None


def _as_event(raw: dict[str, Any], *, index: int, session_id: str) -> TraceEvent:
    kind = str(raw.get("kind") or raw.get("type") or "turn")
    ts = raw.get("timestamp") or raw.get("ts")
    parsed: datetime | None = None
    if isinstance(ts, datetime):
        parsed = ts
    elif isinstance(ts, str):
        try:
            parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    usage_raw = raw.get("token_usage") or raw.get("usage") or {}
    usage = TokenUsage.model_validate(usage_raw) if isinstance(usage_raw, dict) else TokenUsage()
    return TraceEvent(
        kind=kind,
        timestamp=parsed,
        session_id=str(raw.get("session_id") or session_id),
        turn=raw.get("turn"),
        trajectory_position=int(raw.get("trajectory_position", index)),
        model=raw.get("model"),
        provider=raw.get("provider"),
        token_usage=usage,
        cost_usd=raw.get("cost_usd") or raw.get("cost"),
        latency_ms=raw.get("latency_ms") or raw.get("latency"),
        tool=raw.get("tool") or raw.get("tool_name"),
        tool_arguments=raw.get("tool_arguments") or raw.get("arguments"),
        result=raw.get("result") or raw.get("tool_result"),
        output=raw.get("output") or raw.get("final_output") or raw.get("text"),
        provenance=raw.get("provenance"),
        state_from=raw.get("state_from"),
        state_to=raw.get("state_to") or raw.get("state"),
    )


def ingest_trace(data: dict[str, Any] | list[Any]) -> NormalizedTrace:
    if isinstance(data, list):
        session_id = "session"
        events_raw = data
        provenance = None
    else:
        session_id = str(data.get("session_id") or data.get("session") or "session")
        events_raw = data.get("events") or data.get("turns") or []
        provenance = data.get("provenance")
        if not events_raw and data.get("kind"):
            events_raw = [data]
    events = [
        _as_event(e if isinstance(e, dict) else {"output": str(e)}, index=i, session_id=session_id)
        for i, e in enumerate(events_raw)
    ]
    return NormalizedTrace(session_id=session_id, events=events, provenance=provenance)


def load_traces(path: Path) -> list[NormalizedTrace]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    traces: list[NormalizedTrace] = []
    try:
        if suffix == ".jsonl":
            for line in text.splitlines():
                if not line.strip():
                    continue
                traces.append(ingest_trace(json.loads(line)))
        else:
            payload = json.loads(text)
            if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "session_id" in payload[0]:
                traces = [ingest_trace(item) for item in payload]
            else:
                traces = [ingest_trace(payload)]
    except json.JSONDecodeError as exc:
        raise SuiteValidationError(f"Invalid trace JSON: {path}: {exc}") from exc
    return traces
