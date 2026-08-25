"""Human-readable trajectory comparison. Terminal, JSON, and Markdown."""

from __future__ import annotations

from typing import Any

from evaltrim.core.manifest import AgentOutput
from evaltrim.traces import NormalizedTrace


def _steps_from_output(output: AgentOutput) -> list[str]:
    if output.trajectory:
        return [s.kind if not s.name else f"{s.kind}:{s.name}" for s in output.trajectory]
    if output.tool_calls:
        names = [c.name for c in output.tool_calls]
        if output.model:
            return ["model", *names]
        return names
    return ["model"] if output.text else []


def _steps_from_trace(trace: NormalizedTrace) -> list[str]:
    out: list[str] = []
    for ev in trace.events:
        if ev.tool:
            out.append(ev.tool)
        elif ev.kind:
            out.append(ev.kind)
    return out


def _lcs_ops(left: list[str], right: list[str]) -> list[tuple[str, str]]:
    """Return alignment ops: equal/removed/added."""
    n, m = len(left), len(right)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if left[i] == right[j] else max(dp[i + 1][j], dp[i][j + 1])
    i = j = 0
    ops: list[tuple[str, str]] = []
    while i < n and j < m:
        if left[i] == right[j]:
            ops.append(("keep", left[i]))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            ops.append(("removed", left[i]))
            i += 1
        else:
            ops.append(("added", right[j]))
            j += 1
    while i < n:
        ops.append(("removed", left[i]))
        i += 1
    while j < m:
        ops.append(("added", right[j]))
        j += 1
    return ops


_HIGH_RISK = {
    "refund",
    "delete",
    "delete_all",
    "transfer",
    "export",
    "send_email",
    "exec",
    "shell",
}
_GUARD = {"verify_customer", "authenticate", "confirm", "lookup_order", "authorize"}


def compare_trajectories(
    baseline: list[str] | AgentOutput | NormalizedTrace,
    candidate: list[str] | AgentOutput | NormalizedTrace,
    *,
    baseline_args: list[dict[str, Any]] | None = None,
    candidate_args: list[dict[str, Any]] | None = None,
    baseline_output: str | None = None,
    candidate_output: str | None = None,
    baseline_states: list[str] | None = None,
    candidate_states: list[str] | None = None,
) -> dict[str, Any]:
    left = _coerce_steps(baseline)
    right = _coerce_steps(candidate)
    if isinstance(baseline, AgentOutput):
        baseline_args = baseline_args or [c.arguments for c in baseline.tool_calls]
        baseline_output = baseline_output if baseline_output is not None else baseline.text
    if isinstance(candidate, AgentOutput):
        candidate_args = candidate_args or [c.arguments for c in candidate.tool_calls]
        candidate_output = candidate_output if candidate_output is not None else candidate.text
    ops = _lcs_ops(left, right)
    removed = [name for op, name in ops if op == "removed"]
    added = [name for op, name in ops if op == "added"]
    skipped_guard = [s for s in removed if any(g in s for g in _GUARD)]
    risky_add = [s for s in added if any(h in s for h in _HIGH_RISK)]
    if skipped_guard or risky_add:
        risk = "HIGH"
    elif removed or added:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    arg_changed = (baseline_args or []) != (candidate_args or [])
    state_changed = (baseline_states or []) != (candidate_states or [])
    final_changed = (baseline_output or "") != (candidate_output or "")
    payload = {
        "baseline": [{"i": i + 1, "step": s} for i, s in enumerate(left)],
        "candidate": [{"i": i + 1, "step": s} for i, s in enumerate(right)],
        "ops": [{"op": op, "step": name} for op, name in ops],
        "removed": removed,
        "added": added,
        "tool_order_changed": left != right,
        "tool_arguments_changed": arg_changed,
        "step_count": {"baseline": len(left), "candidate": len(right)},
        "state_transitions_changed": state_changed,
        "final_output_changed": final_changed,
        "risk": risk,
        "why": _why(removed, added, skipped_guard, risk),
        "recommended_action": "REVIEW" if risk != "LOW" else "ACCEPT",
    }
    return payload


def _coerce_steps(value: list[str] | AgentOutput | NormalizedTrace) -> list[str]:
    if isinstance(value, AgentOutput):
        return _steps_from_output(value)
    if isinstance(value, NormalizedTrace):
        return _steps_from_trace(value)
    return [str(x) for x in value]


def _why(removed: list[str], added: list[str], skipped_guard: list[str], risk: str) -> str:
    if skipped_guard:
        return "Guard or verification steps were removed before a side-effecting action."
    if removed and added:
        return "Trajectory steps were replaced; inspect argument and state diffs."
    if removed:
        return "Steps were removed from the baseline trajectory."
    if added:
        return "New steps appeared in the candidate trajectory."
    return "Trajectories match at the step-name level."


def render_trajectory_diff(payload: dict[str, Any], *, fmt: str = "markdown") -> str:
    if fmt == "json":
        import json

        return json.dumps(payload, indent=2)
    lines = [
        "# Trajectory diff",
        "",
        "## Baseline",
    ]
    for row in payload["baseline"]:
        lines.append(f"{row['i']}. {row['step']}")
    lines += ["", "## Candidate"]
    for row in payload["candidate"]:
        lines.append(f"{row['i']}. {row['step']}")
    lines += ["", "## Changes"]
    for step in payload["removed"]:
        lines.append(f"REMOVED STEP: {step}")
    for step in payload["added"]:
        lines.append(f"NEW STEP: {step}")
    if not payload["removed"] and not payload["added"]:
        lines.append("No step-level changes.")
    lines += [
        "",
        f"WHAT: trajectory comparison "
        f"({payload['step_count']['baseline']} → {payload['step_count']['candidate']} steps)",
        f"WHY: {payload['why']}",
        (
            f"EVIDENCE: removed={payload['removed']} added={payload['added']} "
            f"args_changed={payload['tool_arguments_changed']}"
        ),
        f"RISK: {payload['risk']}",
        f"RECOMMENDED ACTION: {payload['recommended_action']}",
        "",
    ]
    return "\n".join(lines)


def load_trajectory_file(path: Any) -> list[str] | AgentOutput | NormalizedTrace:
    import json
    from pathlib import Path

    from evaltrim.traces import load_traces

    text = Path(path).read_text(encoding="utf-8")
    suffix = Path(path).suffix.lower()
    if suffix in {".json", ".jsonl"}:
        data = json.loads(text.splitlines()[0] if suffix == ".jsonl" else text)
        if isinstance(data, list) and (not data or isinstance(data[0], str)):
            return [str(s) for s in data]
        if isinstance(data, dict) and "steps" in data:
            return [str(s) for s in data["steps"]]
        if isinstance(data, dict) and "text" in data:
            return AgentOutput.model_validate(data)
        try:
            traces = load_traces(Path(path))
            if traces:
                return traces[0]
        except Exception:  # noqa: BLE001
            pass
        if isinstance(data, list):
            return [str(s) for s in data]
    return [line.strip() for line in text.splitlines() if line.strip()]
