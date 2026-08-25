"""Load and validate YAML/JSON suites into the canonical TestSuite model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from evaltrim.errors import SuiteNotFoundError, SuiteValidationError
from evaltrim.models import AnalysisConfig, TestSuite


def load_suite(path: str | Path) -> TestSuite:
    file_path = Path(path)
    if not file_path.exists():
        raise SuiteNotFoundError(f"Suite not found: {file_path}")
    try:
        raw = file_path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise SuiteValidationError(f"Permission denied reading suite: {file_path}") from exc
    except OSError as exc:
        raise SuiteValidationError(f"Unable to read suite: {file_path}") from exc
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise SuiteValidationError(f"Failed to parse {file_path}: {exc}") from exc
    return parse_suite(data, source=str(file_path))


def parse_suite(data: Any, *, source: str = "<memory>") -> TestSuite:
    if data is None:
        raise SuiteValidationError(f"Empty suite: {source}")
    if not isinstance(data, dict):
        raise SuiteValidationError(f"Suite root must be a mapping, got {type(data).__name__}")
    payload = dict(data)
    if "config" in payload and isinstance(payload["config"], dict):
        try:
            payload["config"] = AnalysisConfig.model_validate(payload["config"])
        except ValidationError as exc:
            raise SuiteValidationError(_format_pydantic(exc, source)) from exc
    try:
        return TestSuite.model_validate(payload)
    except ValidationError as exc:
        raise SuiteValidationError(_format_pydantic(exc, source)) from exc


def dump_suite(suite: TestSuite) -> dict[str, Any]:
    return suite.model_dump(mode="json", exclude_none=True)


def _format_pydantic(exc: ValidationError, source: str) -> str:
    lines = [f"Invalid suite ({source}):"]
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        lines.append(f"  - {loc}: {err.get('msg')}")
    return "\n".join(lines)
