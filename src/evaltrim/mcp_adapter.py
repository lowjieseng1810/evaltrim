"""Tiny optional MCP-style tool adapter. Not a platform. Not required."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaltrim.analyze import analyze_suite, build_maintenance
from evaltrim.explain import explain_test
from evaltrim.impacted import impacted_tests
from evaltrim.parser import load_suite
from evaltrim.regression.compare import compare_analysis
from evaltrim.status import project_status

TOOLS = ("get_status", "impacted_tests", "explain", "regression_summary", "suggest_maintenance")


def dispatch(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool not in TOOLS:
        return {"error": f"unknown tool {tool}", "supported": list(TOOLS)}
    suite_path = Path(arguments["suite"])
    suite = load_suite(suite_path)
    if tool == "get_status":
        return project_status(suite)
    if tool == "impacted_tests":
        return {"tests": impacted_tests(suite, list(arguments.get("paths") or []))}
    if tool == "explain":
        return explain_test(suite, str(arguments["test_id"]))
    if tool == "regression_summary":
        other = load_suite(Path(arguments["baseline"]))
        return compare_analysis(analyze_suite(other), analyze_suite(suite))
    report = build_maintenance(analyze_suite(suite))
    return {
        "keep": report.summary.keep,
        "merge": report.summary.merge,
        "retire": report.summary.retire,
        "review": report.summary.review,
        "notes": report.notes,
    }
