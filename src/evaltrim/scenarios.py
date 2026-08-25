"""Declarative multi-turn scenarios with personas, state, and branching."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult, GraderSpec, Message
from evaltrim.evaluation.graders import grade_record, overall_pass
from evaltrim.runtime.adapters import AgentAdapter, EchoExpectedAdapter

PERSONAS = ("normal", "ambiguous", "adversarial", "persistent", "confused")


class ScenarioTurn(BaseModel):
    user: str | None = None
    expected: str | None = None
    graders: list[GraderSpec] = Field(default_factory=list)
    expect_state: dict[str, Any] | None = None
    tool: dict[str, Any] | None = None
    assertion: dict[str, Any] | None = None
    branch: dict[str, Any] | None = None
    set_state: dict[str, Any] | None = None


class Scenario(BaseModel):
    id: str
    persona: str = "normal"
    style: str = "cooperative"
    turns: list[ScenarioTurn] = Field(default_factory=list)
    steps: list[ScenarioTurn] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    end_state: dict[str, Any] | None = None

    def iter_steps(self) -> list[ScenarioTurn]:
        return list(self.steps or self.turns)


def load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if isinstance(raw, dict) and "scenario" in raw:
        raw = raw["scenario"]
    if isinstance(raw, dict) and "steps" in raw and "turns" not in raw:
        raw = {**raw, "turns": raw["steps"]}
    return Scenario.model_validate(raw)


def replay_scenario(scenario: Scenario, adapter: AgentAdapter | None = None) -> dict[str, Any]:
    adapter = adapter or EchoExpectedAdapter()
    history: list[Message] = []
    rows = []
    state = dict(scenario.state)
    for i, turn in enumerate(scenario.iter_steps()):
        if turn.branch:
            when = turn.branch.get("when") or {}
            if any(state.get(k) != v for k, v in when.items()):
                rows.append({"turn": i, "skipped": True, "branch": when})
                continue
        if turn.set_state:
            state.update(turn.set_state)
            if turn.tool:
                name = str(turn.tool.get("name") or "tool")
                tools = list(state.get("tools") or [])
                tools.append(name)
                state["tools"] = tools
                state["last_tool"] = name
        user = turn.user or ""
        graders = list(turn.graders)
        if turn.assertion:
            if "contains" in turn.assertion:
                graders.append(GraderSpec(type="contains", params={"text": turn.assertion["contains"]}))
            if "equals" in turn.assertion and turn.expected is None:
                turn.expected = str(turn.assertion["equals"])
                graders.append(GraderSpec(type="exact"))
        if turn.expect_state:
            graders.append(GraderSpec(type="state_predicate", params={"equals": turn.expect_state}))
        record = EvaluationRecord(
            id=f"{scenario.id}:{i}",
            input=user,
            expected=turn.expected,
            messages=list(history),
            graders=graders or ([GraderSpec(type="contains")] if turn.expected else []),
            metadata={"persona": scenario.persona, "style": scenario.style, "state": state},
        )
        output: AgentOutput = adapter.run(record) if user or turn.expected else AgentOutput(text="")
        if turn.tool and not output.tool_calls:
            from evaltrim.core.manifest import ToolCallRecord

            output.tool_calls = [
                ToolCallRecord(name=str(turn.tool.get("name")), arguments=dict(turn.tool.get("arguments") or {}))
            ]
        grades: list[GradeResult] = grade_record(record, output) if record.graders else []
        if user:
            history.append(Message(role="user", content=user))
            history.append(Message(role="assistant", content=output.text))
        rows.append(
            {
                "turn": i,
                "passed": overall_pass(grades) if grades else None,
                "output": output.text,
                "state": dict(state),
                "tool": turn.tool,
            }
        )
    end_ok = True
    if scenario.end_state:
        end_ok = all(state.get(k) == v for k, v in scenario.end_state.items())
    return {
        "scenario_id": scenario.id,
        "persona": scenario.persona,
        "style": scenario.style,
        "turns": rows,
        "end_state": state,
        "end_state_ok": end_ok,
        "reproducibility": 1.0 if adapter.name.startswith("echo") else None,
        "note": (
            "Replay is deterministic for echo adapters. Live agents may vary. "
            "LOCAL scenario runner, not a hosted simulator."
        ),
    }
