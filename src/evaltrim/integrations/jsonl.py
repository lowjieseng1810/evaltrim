"""JSONL importer → TestSuite / EvaluationRecord."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaltrim.core.manifest import EvaluationRecord
from evaltrim.errors import SuiteValidationError
from evaltrim.models import Tags, TestCase, TestSuite
from evaltrim.parser import dump_suite


def _row_to_case(row: dict[str, Any], index: int) -> TestCase:
    tid = str(row.get("id") or row.get("test_id") or f"jsonl-{index:04d}")
    inp = row.get("input") or row.get("prompt") or row.get("query")
    exp = row.get("expected") or row.get("output") or row.get("ideal") or ""
    if inp is None:
        raise SuiteValidationError(f"JSONL row {index} missing input/prompt")
    tags = row.get("tags") or {}
    return TestCase(
        id=tid,
        input=str(inp),
        expected=str(exp),
        tags=Tags.model_validate(tags) if isinstance(tags, dict) else Tags(),
        metadata={"source": "jsonl", **(row.get("metadata") or {})},
        requirement_ids=list(row.get("requirement_ids") or []),
    )


def import_jsonl(path: Path) -> TestSuite:
    tests: list[TestCase] = []
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise SuiteValidationError(f"Empty JSONL: {path}")
    for i, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuiteValidationError(f"{path}:{i}: {exc}") from exc
        if not isinstance(row, dict):
            raise SuiteValidationError(f"{path}:{i}: row must be an object")
        tests.append(_row_to_case(row, i))
    return TestSuite(name=path.stem, tests=tests, description=f"Imported from {path.name}")


def import_jsonl_records(path: Path) -> list[EvaluationRecord]:
    suite = import_jsonl(path)
    return [EvaluationRecord.from_test_case(t) for t in suite.tests]


def write_suite(suite: TestSuite, dest: Path) -> None:
    dest.write_text(json.dumps(dump_suite(suite), indent=2), encoding="utf-8")
