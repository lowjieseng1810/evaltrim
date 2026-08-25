import json

from evaltrim.analyze import analyze_suite, build_maintenance
from evaltrim.parser import parse_suite
from evaltrim.reports import render_github_comment, render_maintenance_markdown, render_markdown


def _mini():
    return parse_suite(
        {
            "name": "mini",
            "critical_behaviors": ["privacy"],
            "tests": [
                {
                    "id": "a",
                    "input": "refund $20",
                    "expected": "pay",
                    "tags": {"domain": "refund", "behavior": ["amount_below_limit"]},
                },
                {
                    "id": "b",
                    "input": "delete my data",
                    "expected": "confirm",
                    "tags": {"domain": "privacy", "behavior": ["destructive"], "critical": True},
                },
            ],
        }
    )


def test_markdown_report_sections():
    result = analyze_suite(_mini())
    md = render_markdown(result)
    assert "# EvalTrim Report" in md
    assert "## Summary" in md
    assert "## Unique Witnesses" in md
    assert "## Methodology" in md
    assert "tests analyzed" in md


def test_github_comment_is_short():
    result = analyze_suite(_mini())
    comment = render_github_comment(result)
    assert comment.startswith("## EvalTrim")
    assert "tests analyzed" in comment
    assert "Critical behavior coverage" in comment
    assert len(comment) < 2000


def test_json_roundtrip_shape():
    result = analyze_suite(_mini())
    data = json.loads(result.model_dump_json())
    assert "recommendations" in data
    assert "coverage" in data


def test_maintenance_artifact():
    result = analyze_suite(_mini())
    report = build_maintenance(result)
    md = render_maintenance_markdown(report)
    assert "Maintenance Report" in md
    assert "never deletes" in md.lower() or "never delete" in md.lower()
