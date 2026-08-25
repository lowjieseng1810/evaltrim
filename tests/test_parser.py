import json
from pathlib import Path

import pytest

from evaltrim.errors import SuiteNotFoundError, SuiteValidationError
from evaltrim.parser import dump_suite, load_suite, parse_suite


def test_parse_yaml_like_dict():
    suite = parse_suite(
        {
            "name": "n",
            "critical_behaviors": ["payment"],
            "tests": [
                {
                    "id": "refund-001",
                    "input": "I want a refund of $600",
                    "expected": "Escalate",
                    "tags": {"domain": "refund", "behavior": ["amount_above_limit"], "critical": True},
                }
            ],
        }
    )
    assert suite.tests[0].tags.domain == "refund"
    assert suite.critical_behaviors == ["payment"]


def test_load_json(tmp_path: Path):
    path = tmp_path / "suite.json"
    path.write_text(
        json.dumps({"tests": [{"id": "a", "input": "i", "expected": "e"}]}),
        encoding="utf-8",
    )
    suite = load_suite(path)
    assert suite.tests[0].id == "a"
    dumped = dump_suite(suite)
    assert dumped["tests"][0]["id"] == "a"


def test_load_yaml(tmp_path: Path):
    path = tmp_path / "suite.yaml"
    path.write_text("tests:\n  - id: z\n    input: i\n    expected: e\n", encoding="utf-8")
    assert load_suite(path).tests[0].id == "z"


def test_missing_file():
    with pytest.raises(SuiteNotFoundError):
        load_suite("/tmp/evaltrim-does-not-exist.yaml")


def test_invalid_yaml(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(":\n  -", encoding="utf-8")
    with pytest.raises(SuiteValidationError):
        load_suite(path)


def test_root_must_be_mapping():
    with pytest.raises(SuiteValidationError, match="mapping"):
        parse_suite([{"id": "a"}])
