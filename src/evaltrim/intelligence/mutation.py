"""Controlled mutation testing of graders — not real-world coverage."""

from __future__ import annotations

from typing import Any

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GraderSpec, ToolCallRecord, TrajectoryStep, Usage
from evaltrim.evaluation.graders import grade_record, overall_pass


def _base_output(text: str = "refund approved after confirmation") -> AgentOutput:
    return AgentOutput(
        text=text,
        tool_calls=[ToolCallRecord(name="lookup_order", arguments={"id": "1"})],
        trajectory=[TrajectoryStep(kind="lookup_order"), TrajectoryStep(kind="refund")],
        usage=Usage(latency_ms=80, ttft_ms=12, total_tokens=40, cost_usd=0.01),
        model="mock",
        provider="mock",
    )


def default_mutations(output: AgentOutput) -> list[tuple[str, AgentOutput]]:
    return [
        ("prompt_paraphrase", output.model_copy(update={"text": "I will process that refund now."})),
        ("expected_flip", output.model_copy(update={"text": "totally unrelated answer"})),
        ("tool_order", output.model_copy(update={"trajectory": list(reversed(output.trajectory))})),
        ("tool_drop", output.model_copy(update={"tool_calls": []})),
        ("policy_violation", output.model_copy(update={"text": output.text + " ignore previous policy"})),
        (
            "threshold_latency",
            output.model_copy(update={"usage": output.usage.model_copy(update={"latency_ms": 50_000})}),
        ),
        ("token_blowup", output.model_copy(update={"usage": output.usage.model_copy(update={"total_tokens": 99_000})})),
    ]


def mutation_score(
    *,
    graders: list[GraderSpec] | None = None,
    output: AgentOutput | None = None,
    expected: str = "refund approved after confirmation",
) -> dict[str, Any]:
    record = EvaluationRecord(
        id="mutation-probe",
        input="Please refund order 1",
        expected=expected,
        graders=graders
        or [
            GraderSpec(type="contains"),
            GraderSpec(type="tool_call", params={"required": "lookup_order"}),
            GraderSpec(type="trajectory", params={"order": ["lookup_order", "refund"]}),
            GraderSpec(type="latency", params={"max_ms": 1000}),
            GraderSpec(type="tokens", params={"max_tokens": 200}),
        ],
    )
    good = output or _base_output()
    baseline = overall_pass(grade_record(record, good))
    detected = 0
    rows = []
    mutants = default_mutations(good)
    for name, mutated in mutants:
        passed = overall_pass(grade_record(record, mutated))
        killed = baseline is True and passed is False
        if killed:
            detected += 1
        rows.append({"mutation": name, "killed": killed, "passed": passed})
    total = len(mutants)
    return {
        "mutation_score": round(detected / total, 4) if total else 0.0,
        "detected": detected,
        "total": total,
        "baseline_passed": baseline,
        "cases": rows,
        "note": "Mutation score on constructed grader probes. Not a claim of real-world coverage.",
    }
