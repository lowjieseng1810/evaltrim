"""Local agent adapters. No network unless a user-supplied command talks to one."""

from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from time import perf_counter

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, Usage


class AgentAdapter(ABC):
    name = "base"

    @abstractmethod
    def run(self, record: EvaluationRecord) -> AgentOutput:
        raise NotImplementedError


class EchoExpectedAdapter(AgentAdapter):
    """Deterministic mock: returns expected text. Used for dry wiring and tests."""

    name = "echo-expected"

    def run(self, record: EvaluationRecord) -> AgentOutput:
        text = record.expected or ""
        return AgentOutput(text=text, usage=Usage(latency_ms=0.0, cost_usd=0.0), provider="mock")


class EchoInputAdapter(AgentAdapter):
    name = "echo-input"

    def run(self, record: EvaluationRecord) -> AgentOutput:
        return AgentOutput(text=record.input, usage=Usage(latency_ms=0.0, cost_usd=0.0), provider="mock")


class CommandAdapter(AgentAdapter):
    """Runs a local command. Sends JSON on stdin, reads JSON or plain text on stdout."""

    name = "command"

    def __init__(self, command: list[str], timeout: float = 30.0) -> None:
        self.command = command
        self.timeout = timeout

    def run(self, record: EvaluationRecord) -> AgentOutput:
        payload = json.dumps({"id": record.id, "input": record.input, "expected": record.expected})
        t0 = perf_counter()
        proc = subprocess.run(
            self.command,
            input=payload,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        latency = (perf_counter() - t0) * 1000
        stdout = proc.stdout.strip()
        text = stdout
        model = None
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and "output" in data:
                text = str(data["output"])
                model = data.get("model")
        except json.JSONDecodeError:
            pass
        return AgentOutput(
            text=text,
            usage=Usage(latency_ms=latency, cost_usd=0.0),
            model=model,
            provider="command",
        )


def resolve_adapter(name: str, command: list[str] | None = None) -> AgentAdapter:
    if name in {"echo-expected", "mock"}:
        return EchoExpectedAdapter()
    if name == "echo-input":
        return EchoInputAdapter()
    if name == "command":
        if not command:
            raise ValueError("command adapter requires --command")
        return CommandAdapter(command)
    raise ValueError(f"unknown adapter {name!r}")
