"""Requirement → behavior → test → run → failure → recommendation graph.

Heuristic links only. User-provided tags remain authoritative.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evaltrim.models import AnalysisResult, TestSuite


def behavior_graph(suite: TestSuite, result: AnalysisResult) -> dict[str, Any]:
    rec_by = {r.test_id: r.state.value for r in result.recommendations}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    for req in suite.requirements:
        nodes.append({"id": f"req:{req.id}", "kind": "requirement", "label": req.id, "critical": req.critical})
    for ev in result.evidence:
        b = ev.behavior
        bid = f"beh:{b.domain}:{b.action}:{','.join(b.conditions)}"
        nodes.append(
            {
                "id": bid,
                "kind": "behavior",
                "domain": b.domain,
                "action": b.action,
                "conditions": list(b.conditions),
                "state": b.state,
                "critical": b.critical,
            }
        )
        nodes.append({"id": f"test:{ev.test_id}", "kind": "test", "label": ev.test_id})
        edges.append({"from": bid, "to": f"test:{ev.test_id}", "rel": "witnessed_by"})
        nodes.append({"id": f"rec:{ev.test_id}", "kind": "recommendation", "label": rec_by.get(ev.test_id, "KEEP")})
        edges.append({"from": f"test:{ev.test_id}", "to": f"rec:{ev.test_id}", "rel": "recommended"})
        if ev.conflict:
            nodes.append({"id": f"fail:{ev.test_id}", "kind": "failure", "label": "oracle_conflict"})
            edges.append({"from": f"test:{ev.test_id}", "to": f"fail:{ev.test_id}", "rel": "failed"})
        for rid in suite.get(ev.test_id).requirement_ids:
            edges.append({"from": f"req:{rid}", "to": bid, "rel": "requires"})

    # Dedupe nodes by id
    uniq: dict[str, dict[str, Any]] = {}
    for node in nodes:
        uniq[node["id"]] = node
    signatures = {
        t.id: {
            "domain": (t.behavior.domain if t.behavior else "unknown"),
            "action": (t.behavior.action if t.behavior else "unknown"),
            "conditions": list(t.behavior.conditions) if t.behavior else [],
            "state": (t.behavior.state if t.behavior else "normal"),
            "critical": bool(t.behavior.critical) if t.behavior else False,
            "source": (t.behavior.source if t.behavior else "unknown"),
        }
        for t in suite.tests
    }
    by_behavior: dict[str, list[str]] = defaultdict(list)
    for tid, sig in signatures.items():
        conds = sig["conditions"]
        cond_s = ",".join(conds) if isinstance(conds, list) else str(conds)
        key = f"{sig['domain']}|{sig['action']}|{cond_s}"
        by_behavior[key].append(tid)
    return {
        "nodes": list(uniq.values()),
        "edges": edges,
        "signatures": signatures,
        "tests_by_behavior": dict(by_behavior),
        "note": "Heuristic graph. Explicit tags override keyword extraction.",
    }
