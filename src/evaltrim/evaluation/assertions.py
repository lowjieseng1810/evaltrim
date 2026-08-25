"""Assertion helpers over AgentOutput. Composed with graders."""

from __future__ import annotations

from evaltrim.core.manifest import AgentOutput, GradeResult


def assert_forbidden_content(output: AgentOutput, phrases: list[str]) -> GradeResult:
    text = output.text.lower()
    hits = [p for p in phrases if p.lower() in text]
    return GradeResult(
        grader="forbidden_content",
        passed=not hits,
        score=0.0 if hits else 1.0,
        detail="ok" if not hits else f"found {hits}",
    )


def assert_max_steps(output: AgentOutput, max_steps: int) -> GradeResult:
    n = len(output.trajectory) or len(output.tool_calls)
    ok = n <= max_steps
    return GradeResult(grader="max_steps", passed=ok, score=1.0 if ok else 0.0, detail=str(n))
