"""Multi-turn scenario model and deterministic replay."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult, GraderSpec, Message
from evaltrim.evaluation.graders import grade_record, overall_pass
from evaltrim.runtime.adapters import AgentAdapter, EchoExpectedAdapter


class ScenarioTurn(BaseModel):
    user: str
    expected: str | None = None
    graders: list[GraderSpec] = Field(default_factory=list)


class Scenario(BaseModel):
    id: str
    persona: str = "neutral"
    style: str = "cooperative"  # cooperative|adversarial|ambiguous|persistent
    turns: list[ScenarioTurn]
    state: dict[str, Any] = Field(default_factory=dict)


def replay_scenario(scenario: Scenario, adapter: AgentAdapter | None = None) -> dict[str, Any]:
    adapter = adapter or EchoExpectedAdapter()
    history: list[Message] = []
    rows = []
    for i, turn in enumerate(scenario.turns):
        record = EvaluationRecord(
            id=f"{scenario.id}:{i}",
            input=turn.user,
            expected=turn.expected,
            messages=list(history),
            graders=turn.graders or ([GraderSpec(type="contains")] if turn.expected else []),
            metadata={"persona": scenario.persona, "style": scenario.style, "state": scenario.state},
        )
        output: AgentOutput = adapter.run(record)
        grades: list[GradeResult] = grade_record(record, output) if record.graders else []
        history.append(Message(role="user", content=turn.user))
        history.append(Message(role="assistant", content=output.text))
        rows.append(
            {
                "turn": i,
                "passed": overall_pass(grades) if grades else None,
                "output": output.text,
            }
        )
    return {
        "scenario_id": scenario.id,
        "persona": scenario.persona,
        "style": scenario.style,
        "turns": rows,
        "reproducibility": 1.0 if adapter.name.startswith("echo") else None,
        "note": "Replay is deterministic for echo adapters. Live agents may vary.",
    }
