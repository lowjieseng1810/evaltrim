"""Repeated-run statistics. Assumptions are documented; this is not a stats package substitute."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any


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


def stdev(values: Sequence[float]) -> float | None:
    var = variance(values)
    return None if var is None else math.sqrt(var)


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= q <= 100.0:
        raise ValueError("percentile q must be in [0, 100]")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (q / 100.0) * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(ordered[lo])
    frac = pos - lo
    return float(ordered[lo] * (1 - frac) + ordered[hi] * frac)


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


def bootstrap_ci(
    values: Sequence[float],
    *,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for the mean. Deterministic given seed."""
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def cohens_d(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2 or len(right) < 2:
        return None
    ml, mr = mean(left), mean(right)
    vl, vr = variance(left), variance(right)
    assert ml is not None and mr is not None and vl is not None and vr is not None
    pooled = math.sqrt(((len(left) - 1) * vl + (len(right) - 1) * vr) / (len(left) + len(right) - 2))
    if pooled == 0:
        return 0.0 if ml == mr else float("inf")
    return (mr - ml) / pooled


def welch_ttest(left: Sequence[float], right: Sequence[float]) -> dict[str, float | None]:
    """Welch's t-test. p-value uses a normal tail for df>40, otherwise a conservative t approximation."""
    if len(left) < 2 or len(right) < 2:
        return {"t": None, "df": None, "p_two_sided": None}
    ml, mr = mean(left), mean(right)
    vl, vr = variance(left), variance(right)
    assert ml is not None and mr is not None and vl is not None and vr is not None
    n1, n2 = len(left), len(right)
    se2 = vl / n1 + vr / n2
    if se2 <= 0:
        t = 0.0 if ml == mr else float("inf")
        return {"t": t, "df": float(n1 + n2 - 2), "p_two_sided": 1.0 if ml == mr else 0.0}
    t = (mr - ml) / math.sqrt(se2)
    num = se2**2
    den = (vl / n1) ** 2 / (n1 - 1) + (vr / n2) ** 2 / (n2 - 1)
    df = num / den if den else float(n1 + n2 - 2)
    p = _two_sided_p(abs(t), df)
    return {"t": t, "df": df, "p_two_sided": p}


def _two_sided_p(t_abs: float, df: float) -> float:
    if df > 40:
        return min(1.0, max(0.0, math.erfc(t_abs / math.sqrt(2.0))))
    # Hill (1970)-style approximation via regularized incomplete beta on x = df/(df+t^2).
    x = df / (df + t_abs * t_abs)
    a = df / 2.0
    b = 0.5
    ib = _regularized_incomplete_beta(x, a, b)
    return min(1.0, max(0.0, ib))


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    # Continued fraction (Lentz) for Ix.
    front = math.exp(a * math.log(x) + b * math.log(1 - x) - ln_beta) / a
    cf = _betacf(x, a, b)
    return min(1.0, max(0.0, front * cf))


def _betacf(x: float, a: float, b: float, max_iter: int = 200) -> float:
    tiny = 1e-30
    am, bm, az = 1.0, 1.0, 1.0
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    bz = 1.0 - qab * x / qap
    for m in range(1, max_iter + 1):
        em = float(m)
        tem = em + em
        d = em * (b - em) * x / ((qam + tem) * (a + tem))
        ap = az + d * am
        bp = bz + d * bm
        d = -(a + em) * (qab + em) * x / ((a + tem) * (qap + tem))
        app = ap + d * az
        bpp = bp + d * bz
        am, bm, az, bz = ap / bpp, bp / bpp, app / bpp, 1.0
        if abs(az - app / (bpp or tiny)) < 3e-7:
            return az
    return az


def compare_samples(
    baseline: Sequence[float],
    current: Sequence[float],
    *,
    alpha: float = 0.05,
    practical_d: float = 0.2,
    practical_relative: float = 0.05,
) -> dict[str, Any]:
    """Distinguish statistically significant vs practically significant mean shifts."""
    welch = welch_ttest(baseline, current)
    d = cohens_d(baseline, current)
    mb, mc = mean(baseline), mean(current)
    rel = None
    if mb is not None and mc is not None:
        denom = max(abs(mb), 1e-12)
        rel = abs(mc - mb) / denom
    p = welch["p_two_sided"]
    stat_sig = p is not None and p < alpha
    prac_sig = (d is not None and abs(d) >= practical_d) or (rel is not None and rel >= practical_relative)
    return {
        "baseline_mean": mb,
        "current_mean": mc,
        "welch": welch,
        "cohens_d": d,
        "relative_change": rel,
        "statistically_significant": stat_sig,
        "practically_significant": prac_sig,
        "regression_flag": bool(stat_sig and prac_sig and mb is not None and mc is not None and mc < mb),
        "note": (
            "Statistical significance is not practical significance. "
            "regression_flag requires both, plus a mean decrease."
        ),
    }


def summarize_runs(pass_flags: Sequence[bool], latencies: Sequence[float]) -> dict[str, float | None | tuple | dict]:
    lats = list(latencies)
    return {
        "n": len(pass_flags),
        "pass_rate": pass_rate(list(pass_flags)),
        "latency_mean": mean(lats),
        "latency_median": median(lats),
        "latency_variance": variance(lats),
        "latency_stdev": stdev(lats),
        "latency_p50": percentile(lats, 50),
        "latency_p90": percentile(lats, 90),
        "latency_p95": percentile(lats, 95),
        "latency_p99": percentile(lats, 99),
        "latency_ci95": normal_ci(lats),
        "latency_bootstrap_ci95": bootstrap_ci(lats),
    }
