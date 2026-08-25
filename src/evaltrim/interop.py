"""Import/export for EvalTrim YAML, JSON, and JSONL. No brittle vendor lock-in."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from evaltrim.integrations.jsonl import import_jsonl, write_suite
from evaltrim.models import TestSuite
from evaltrim.parser import dump_suite, load_suite, parse_suite


def export_suite(suite: TestSuite, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = dest.suffix.lower()
    payload = dump_suite(suite)
    if suffix == ".json":
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif suffix in {".jsonl", ".ndjson"}:
        lines = []
        for test in suite.tests:
            lines.append(json.dumps(test.model_dump(mode="json"), default=str))
        dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        dest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return dest


def import_suite(source: Path) -> TestSuite:
    suffix = source.suffix.lower()
    if suffix in {".jsonl", ".ndjson"}:
        return import_jsonl(source)
    return load_suite(source)


def from_promptfoo_like(rows: list[dict[str, Any]]) -> TestSuite:
    """Best-effort map of {prompt, assert/expected} rows. Not a full Promptfoo runtime."""
    tests = []
    from evaltrim.models import Tags, TestCase

    for i, row in enumerate(rows):
        inp = str(row.get("prompt") or row.get("input") or row.get("vars", {}).get("query") or "")
        exp = str(row.get("expected") or row.get("assert") or row.get("output") or "")
        tests.append(
            TestCase(
                id=str(row.get("id") or f"pf-{i:04d}"),
                input=inp,
                expected=exp if not isinstance(exp, list) else json.dumps(exp),
                tags=Tags(),
                metadata={"imported_from": "promptfoo-like"},
            )
        )
    return TestSuite(name="imported", tests=tests)


__all__ = ["export_suite", "from_promptfoo_like", "import_suite", "parse_suite", "write_suite"]
