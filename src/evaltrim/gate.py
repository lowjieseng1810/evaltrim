"""evaltrim gate — fast pre-commit / pre-push checks. Not a full suite run."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from evaltrim.analyze import analyze_suite
from evaltrim.errors import StrictModeError
from evaltrim.impacted import impacted_tests
from evaltrim.models import RecommendationState, TestSuite
from evaltrim.policy import evaluate_policies


def git_changed_paths(repo: Path, *, base: str = "HEAD") -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def gate(
    suite: TestSuite,
    *,
    changed_paths: list[str] | None = None,
    repo: Path | None = None,
    fast: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    paths = list(changed_paths or [])
    if not paths and repo is not None:
        paths = git_changed_paths(repo)
    result = analyze_suite(suite)
    rows = impacted_tests(suite, paths or ["."])
    selected: list[str] = []
    for row in rows:
        if row["priority"] in {"CRITICAL", "DIRECT", "RISKY"}:
            selected.append(str(row["test_id"]))
    high_risk = [
        r.test_id for r in result.recommendations if r.state == RecommendationState.REVIEW and r.test_id in selected
    ]
    # Small safety sample: first two unique critical witnesses.
    sample = [w.test_id for w in result.witnesses if w.unique_critical][:2]
    if not fast:
        selected.extend(sample)
    selected = sorted(set(selected + high_risk + sample[:1]))
    problems = evaluate_policies(result, suite.config.policies) if strict else []
    payload = {
        "mode": "fast" if fast else "standard",
        "strict": strict,
        "changed_paths": paths,
        "selected_tests": selected[:40],
        "impacted": [r for r in rows if r["priority"] != "LOW_PRIORITY"][:40],
        "problems": problems,
        "note": "Gate does not run the agent. It selects impacted/critical cases for review.",
    }
    if strict and problems:
        raise StrictModeError("Gate failed:\n- " + "\n- ".join(problems))
    return payload
