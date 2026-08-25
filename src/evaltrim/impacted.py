"""Impacted-test selection. Heuristic, not perfect dependency analysis."""

from __future__ import annotations

from pathlib import Path

from evaltrim.models import ImpactPriority, TestSuite


def impacted_tests(suite: TestSuite, changed_paths: list[str]) -> list[dict[str, object]]:
    norms = [_norm(p) for p in changed_paths]
    rows: list[dict[str, object]] = []
    direct: set[str] = set()
    adjacent: set[str] = set()
    evidence: dict[str, list[str]] = {t.id: [] for t in suite.tests}
    for test in suite.tests:
        files = [_norm(p) for p in test.provenance_files]
        tools = [t.lower() for t in test.tool_dependencies]
        hit_file = any(any(n in f or f in n or Path(n).name == Path(f).name for n in norms) for f in files)
        hit_tool = any(
            any(Path(n).stem.lower() in tool or tool in Path(n).stem.lower() for n in norms) for tool in tools
        )
        hit_req = any(any(rid.lower() in n.lower() for n in norms) for rid in test.requirement_ids)
        if hit_file:
            direct.add(test.id)
            evidence[test.id].append("provenance_file")
        if hit_tool:
            direct.add(test.id)
            evidence[test.id].append("tool_dependency")
        if hit_req:
            adjacent.add(test.id)
            evidence[test.id].append("requirement_id")
        elif test.tags.domain and any(test.tags.domain.lower() in n.lower() for n in norms):
            adjacent.add(test.id)
            evidence[test.id].append("domain_in_path")

    families = {t.id: t.failure_family for t in suite.tests if t.failure_family}
    direct_families = {families[tid] for tid in direct if tid in families}
    for test in suite.tests:
        if test.id not in direct and test.failure_family and test.failure_family in direct_families:
            adjacent.add(test.id)
            evidence[test.id].append("shared_failure_family")

    for test in suite.tests:
        critical = test.tags.critical or (test.behavior and test.behavior.critical)
        if test.id in direct and critical:
            priority = ImpactPriority.CRITICAL
        elif test.id in adjacent and critical:
            priority = ImpactPriority.CRITICAL
        elif test.id in direct:
            priority = ImpactPriority.DIRECT
        elif test.id in adjacent and (test.quarantined or test.failure_family):
            priority = ImpactPriority.RISKY
        elif test.id in adjacent:
            priority = ImpactPriority.ADJACENT
        else:
            priority = ImpactPriority.LOW_PRIORITY
        rows.append(
            {
                "test_id": test.id,
                "priority": priority.value,
                "evidence": evidence[test.id],
                "note": "Heuristic; not a complete call graph.",
            }
        )
    order = {"CRITICAL": 0, "DIRECT": 1, "RISKY": 2, "ADJACENT": 3, "LOW_PRIORITY": 4}
    rows.sort(key=lambda r: (order[str(r["priority"])], str(r["test_id"])))
    return rows


def _norm(path: str) -> str:
    return Path(path.replace("\\", "/")).as_posix().lower()
