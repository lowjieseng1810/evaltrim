"""Behavioral equivalence classes. Deterministic clustering, not a learned embedding clusterer."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evaltrim.models import AnalysisResult, TestSuite

_STATE_ORDER = ("destructive", "adversarial", "ambiguous", "boundary", "negative", "normal")


def _leaf(test) -> str:
    conds = {c.lower() for c in (test.behavior.conditions if test.behavior else test.tags.behavior)}
    for name in _STATE_ORDER[:-1]:
        if any(name in c for c in conds):
            return name
    if test.tags.critical:
        return "critical"
    return "normal"


def cluster_behaviors(suite: TestSuite, result: AnalysisResult | None = None) -> dict[str, Any]:
    tree: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for test in suite.tests:
        domain = (test.behavior.domain if test.behavior else test.tags.domain) or "unknown"
        tree[domain][_leaf(test)].append(test.id)
    clusters = []
    for domain in sorted(tree):
        children = tree[domain]
        for leaf in sorted(children):
            ids = sorted(children[leaf])
            clusters.append(
                {
                    "class_id": f"{domain}/{leaf}",
                    "domain": domain,
                    "leaf": leaf,
                    "test_ids": ids,
                    "size": len(ids),
                }
            )
    purity = 1.0
    if clusters:
        # Labels are the assigned leaves; purity vs domain is 1.0 by construction of the tree.
        purity = 1.0
    return {
        "clusters": clusters,
        "class_count": len(clusters),
        "class_purity": purity,
        "cluster_stability": 1.0,
        "note": (
            "Classes are deterministic tag/behavior partitions (domain × state leaf). "
            "Stability is 1.0 because the assignment has no random init. "
            "This is not an embedding clustering purity score against an external gold set unless provided."
        ),
    }


def cluster_recall_against(gold: dict[str, str], predicted: list[dict[str, Any]]) -> float:
    """Recall of gold class labels recovered as domain/leaf. Gold maps test_id → class string."""
    pred: dict[str, str] = {}
    for row in predicted:
        for tid in row["test_ids"]:
            pred[tid] = row["class_id"]
    if not gold:
        return 1.0
    hits = 0
    for tid, label in gold.items():
        got = pred.get(tid, "")
        if label == got or label in got or got.endswith("/" + label):
            hits += 1
    return hits / len(gold)
