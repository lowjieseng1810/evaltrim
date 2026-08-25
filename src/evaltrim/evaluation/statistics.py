"""Descriptive statistics for multi-run results. Assumptions are documented, not implied."""

from __future__ import annotations

import math
from collections.abc import Sequence


def mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def variance(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    m = mean(values)
    assert m is not None
    return sum((v - m) ** 2 for v in values) / (len(values) - 1)


def pass_rate(flags: Sequence[bool]) -> float | None:
    if not flags:
        return None
    return sum(1 for f in flags if f) / len(flags)


def normal_ci(values: Sequence[float], z: float = 1.96) -> tuple[float, float] | None:
    """Wald interval around the mean. Assumes i.i.d. samples; not valid for n<2."""
    if len(values) < 2:
        return None
    m = mean(values)
    var = variance(values)
    assert m is not None and var is not None
    se = math.sqrt(var / len(values))
    return (m - z * se, m + z * se)


def summarize_runs(pass_flags: Sequence[bool], latencies: Sequence[float]) -> dict[str, float | None | tuple]:
    return {
        "n": len(pass_flags),
        "pass_rate": pass_rate(list(pass_flags)),
        "latency_mean": mean(list(latencies)),
        "latency_median": median(list(latencies)),
        "latency_variance": variance(list(latencies)),
        "latency_ci95": normal_ci(list(latencies)),
    }
