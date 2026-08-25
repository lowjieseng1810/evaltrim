"""Load optional evaltrim.yaml policy files and evaluate CI gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from evaltrim.errors import EvalTrimError, StrictModeError, SuiteValidationError
from evaltrim.models import AnalysisConfig, AnalysisResult, SafetyPolicies


class PolicyError(EvalTrimError):
    """Invalid policy file."""

    exit_code = 2


def load_policy_file(path: str | Path | None) -> AnalysisConfig | None:
    if path is None:
        return None
    file_path = Path(path)
    if not file_path.exists():
        raise PolicyError(f"Policy file not found: {file_path}")
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PolicyError(f"Policy file is not valid YAML: {file_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyError("Policy file root must be a mapping")
    payload: dict[str, Any] = dict(data)
    if "policies" in payload and "config" not in payload:
        payload = {"policies": payload["policies"], **{k: v for k, v in payload.items() if k != "policies"}}
        # Allow a flat {policies: ...} or full AnalysisConfig.
        try:
            if set(payload) <= {"policies", "weights", "redundancy_threshold", "merge_threshold", "stale_days"}:
                return AnalysisConfig.model_validate(payload)
        except ValidationError as exc:
            raise PolicyError(str(exc)) from exc
    try:
        if "config" in payload and isinstance(payload["config"], dict):
            return AnalysisConfig.model_validate(payload["config"])
        return AnalysisConfig.model_validate(payload)
    except ValidationError as exc:
        raise PolicyError(f"Invalid policy file: {exc}") from exc


def discover_policy(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for _ in range(6):
        candidate = here / "evaltrim.yaml"
        if candidate.exists():
            return candidate
        if here.parent == here:
            break
        here = here.parent
    return None


def merge_config(base: AnalysisConfig, overlay: AnalysisConfig | None) -> AnalysisConfig:
    if overlay is None:
        return base
    data = base.model_dump()
    over = overlay.model_dump()
    data["policies"] = over.get("policies", data["policies"])
    for key in (
        "redundancy_threshold",
        "merge_threshold",
        "stale_days",
        "embeddings_enabled",
        "llm_enabled",
        "full_pairwise_limit",
        "candidate_neighbor_k",
    ):
        if key in over:
            data[key] = over[key]
    return AnalysisConfig.model_validate(data)


def evaluate_policies(result: AnalysisResult, policies: SafetyPolicies) -> list[str]:
    problems: list[str] = []
    if result.coverage.critical_coverage + 1e-9 < policies.minimum_critical_coverage:
        problems.append(
            f"critical coverage {result.coverage.critical_coverage:.3f} "
            f"< minimum {policies.minimum_critical_coverage:.3f}"
        )
    if result.coverage.uncovered_critical:
        problems.append("uncovered critical behaviors: " + ", ".join(result.coverage.uncovered_critical))
    if policies.fail_on_oracle_conflict and result.conflicts:
        problems.append("oracle conflicts: " + ", ".join(result.conflicts))
    return problems


def assert_policies(result: AnalysisResult, policies: SafetyPolicies) -> None:
    problems = evaluate_policies(result, policies)
    if problems:
        raise StrictModeError("Policy check failed:\n- " + "\n- ".join(problems))


def validate_policies_object(data: Any) -> SafetyPolicies:
    try:
        return SafetyPolicies.model_validate(data)
    except ValidationError as exc:
        raise SuiteValidationError(str(exc)) from exc
