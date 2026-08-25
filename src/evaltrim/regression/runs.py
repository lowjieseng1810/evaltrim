"""Compare recorded agent runs. Not every difference is a regression."""

from __future__ import annotations

from typing import Any

from evaltrim.models import DriftSource, RegressionClass
from evaltrim.normalize import normalize_text
from evaltrim.similarity import jaccard, tokenize_normalized


def _text_sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if normalize_text(a) == normalize_text(b) and normalize_text(a):
        return 0.97
    return jaccard(tokenize_normalized(a), tokenize_normalized(b))


def classify_run_delta(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    expected_change_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Classify one case delta with evidence. Does not claim true causation."""
    evidence: list[str] = []
    out_b = str(baseline.get("output") or baseline.get("text") or "")
    out_c = str(current.get("output") or current.get("text") or "")
    sem = _text_sim(out_b, out_c)
    tools_b = baseline.get("tool_calls") or []
    tools_c = current.get("tool_calls") or []
    args_b = baseline.get("tool_arguments") or []
    args_c = current.get("tool_arguments") or []
    traj_b = baseline.get("trajectory") or []
    traj_c = current.get("trajectory") or []
    raw_b = baseline.get("grader_score")
    raw_c = current.get("grader_score")
    score_b = float(raw_b) if raw_b is not None else (1.0 if baseline.get("passed") else 0.0)
    score_c = float(raw_c) if raw_c is not None else (1.0 if current.get("passed") else 0.0)
    lat_b = float(baseline.get("latency_ms") or 0.0)
    lat_c = float(current.get("latency_ms") or 0.0)
    cost_b = float(baseline.get("cost_usd") or 0.0)
    cost_c = float(current.get("cost_usd") or 0.0)
    tok_b = int(baseline.get("tokens") or 0)
    tok_c = int(current.get("tokens") or 0)

    passed_b = bool(baseline.get("passed", True))
    passed_c = bool(current.get("passed", True))
    oracle_b = str(baseline.get("expected") or "")
    oracle_c = str(current.get("expected") or "")
    oracle_changed = oracle_b != oracle_c and bool(oracle_b or oracle_c)

    channels = {
        "output_equal": out_b == out_c,
        "semantic_output": round(sem, 4),
        "tool_calls_equal": tools_b == tools_c,
        "tool_arguments_equal": args_b == args_c,
        "trajectory_equal": traj_b == traj_c,
        "grader_scores": {"before": score_b, "after": score_c},
        "latency_ms": {"before": lat_b, "after": lat_c},
        "cost_usd": {"before": cost_b, "after": cost_c},
        "tokens": {"before": tok_b, "after": tok_c},
        "oracle_changed": oracle_changed,
        "agent_changed": out_b != out_c or tools_b != tools_c,
    }

    if oracle_changed and passed_b == passed_c and sem >= 0.9:
        klass = RegressionClass.EXPECTED_CHANGE
        evidence.append("Oracle text changed while agent output stayed semantically close.")
    elif expected_change_paths:
        klass = RegressionClass.EXPECTED_CHANGE
        evidence.append("Caller marked this delta as an expected change via changed paths.")
    elif passed_b and not passed_c and sem < 0.6:
        klass = RegressionClass.CONFIRMED_REGRESSION
        evidence.append("Previously passing case now fails with a large output shift.")
    elif passed_b and not passed_c:
        klass = RegressionClass.POSSIBLE_REGRESSION
        evidence.append("Pass→fail without a large semantic shift; could be flake or grader tightness.")
    elif not passed_b and passed_c:
        klass = RegressionClass.EXPECTED_CHANGE
        evidence.append("Fail→pass; treated as an improvement unless policy says otherwise.")
    elif out_b != out_c and passed_b and passed_c:
        klass = RegressionClass.UNCERTAIN
        evidence.append("Output changed but graders still pass.")
    else:
        klass = RegressionClass.UNCERTAIN
        evidence.append("Insufficient signal to call a regression.")

    drift = classify_drift_source(baseline, current, oracle_changed=oracle_changed)
    return {
        "class": klass.value,
        "likely_source": drift["source"],
        "likely_source_confidence": drift["confidence"],
        "evidence": evidence,
        "channels": channels,
        "note": "LIKELY_SOURCE is a heuristic, not causal attribution.",
    }


def classify_drift_source(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    oracle_changed: bool,
) -> dict[str, Any]:
    model_b, model_c = baseline.get("model"), current.get("model")
    provider_b, provider_c = baseline.get("provider"), current.get("provider")
    schema_b, schema_c = baseline.get("tool_schema"), current.get("tool_schema")
    prompt_b, prompt_c = baseline.get("prompt_hash"), current.get("prompt_hash")
    config_b, config_c = baseline.get("config_hash"), current.get("config_hash")
    code_b, code_c = baseline.get("code_hash"), current.get("code_hash")

    if oracle_changed and prompt_b == prompt_c and model_b == model_c:
        return {"source": DriftSource.TEST_ORACLE_CHANGE.value, "confidence": 0.72}
    if model_b != model_c or provider_b != provider_c:
        return {"source": DriftSource.MODEL_PROVIDER_CHANGE.value, "confidence": 0.7}
    if schema_b != schema_c and schema_b is not None:
        return {"source": DriftSource.TOOL_SCHEMA_CHANGE.value, "confidence": 0.68}
    if prompt_b != prompt_c and prompt_b is not None:
        return {"source": DriftSource.PROMPT_CHANGE.value, "confidence": 0.66}
    if config_b != config_c and config_b is not None:
        return {"source": DriftSource.CONFIGURATION_CHANGE.value, "confidence": 0.64}
    if code_b != code_c and code_b is not None:
        return {"source": DriftSource.CODE_CHANGE.value, "confidence": 0.62}
    return {"source": DriftSource.UNCERTAIN.value, "confidence": 0.35}


def compare_runs(baseline_cases: list[dict[str, Any]], current_cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_b = {str(c.get("id") or c.get("record_id")): c for c in baseline_cases}
    by_c = {str(c.get("id") or c.get("record_id")): c for c in current_cases}
    ids = sorted(set(by_b) | set(by_c))
    rows = []
    counts: dict[str, int] = {k.value: 0 for k in RegressionClass}
    for cid in ids:
        if cid not in by_b or cid not in by_c:
            rows.append(
                {
                    "id": cid,
                    "class": RegressionClass.UNCERTAIN.value,
                    "evidence": ["Case missing on one side."],
                }
            )
            counts[RegressionClass.UNCERTAIN.value] += 1
            continue
        delta = classify_run_delta(by_b[cid], by_c[cid])
        delta["id"] = cid
        rows.append(delta)
        counts[delta["class"]] += 1
    return {
        "cases": rows,
        "counts": counts,
        "note": "Differences are classified with evidence; not every delta is a regression.",
    }
