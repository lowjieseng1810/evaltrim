"""Plugin graders. Default path is local and deterministic. LLM judge is opt-in skip."""

from __future__ import annotations

import importlib
import json
import re
from abc import ABC, abstractmethod
from typing import Any

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult, GraderSpec
from evaltrim.similarity import cosine, tokenize_normalized

REGISTRY: dict[str, type[Grader]] = {}


class Grader(ABC):
    name = "base"

    @abstractmethod
    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        raise NotImplementedError


def register_grader(cls: type[Grader], *, aliases: tuple[str, ...] = ()) -> type[Grader]:
    """Register a grader plugin. Built-ins call this at import time."""
    REGISTRY[cls.name] = cls
    for alias in aliases:
        REGISTRY[alias] = cls
    return cls


class ExactMatchGrader(Grader):
    name = "exact"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        expected = (record.expected or spec.params.get("expected") or "").strip()
        actual = output.text.strip()
        ok = actual == expected
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail="exact string match")


class ContainsGrader(Grader):
    name = "contains"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        needle = str(spec.params.get("text") or record.expected or "")
        if not needle:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no expected text")
        ok = needle.lower() in output.text.lower()
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"contains {needle[:80]!r}")


class NotContainsGrader(Grader):
    name = "not_contains"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        needle = str(spec.params.get("text") or "")
        if not needle:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no forbidden text")
        ok = needle.lower() not in output.text.lower()
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"forbids {needle[:80]!r}")


class RegexGrader(Grader):
    name = "regex"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        pattern = str(spec.params.get("pattern") or record.expected or "")
        try:
            ok = re.search(pattern, output.text, flags=re.IGNORECASE) is not None
        except re.error as exc:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"invalid regex: {exc}")
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=pattern)


def _json_schema_errors(data: Any, schema: dict[str, Any], *, path: str = "$") -> list[str]:
    """Minimal JSON Schema subset: type, required, properties, additionalProperties, enum."""
    errors: list[str] = []
    expected_type = schema.get("type")
    type_map: dict[str, type | tuple[type, ...]] = {
        "object": dict,
        "array": list,
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "null": type(None),
    }
    if expected_type in type_map:
        py = type_map[expected_type]
        if expected_type == "number" and isinstance(data, bool):
            errors.append(f"{path}: expected number")
        elif not isinstance(data, py) or (expected_type == "integer" and isinstance(data, bool)):
            errors.append(f"{path}: expected {expected_type}")
            return errors
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(data, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in data:
                errors.append(f"{path}: missing {key}")
        props = schema.get("properties") or {}
        additional = schema.get("additionalProperties", True)
        for key, value in data.items():
            if key in props:
                errors.extend(_json_schema_errors(value, props[key], path=f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}: unexpected {key}")
    if isinstance(data, list) and "items" in schema and isinstance(schema["items"], dict):
        for i, item in enumerate(data):
            errors.extend(_json_schema_errors(item, schema["items"], path=f"{path}[{i}]"))
    return errors


class JsonSchemaGrader(Grader):
    name = "json"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        try:
            data = json.loads(output.text)
        except json.JSONDecodeError as exc:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=str(exc))
        schema = spec.params.get("schema")
        if isinstance(schema, dict):
            errors = _json_schema_errors(data, schema)
            ok = not errors
            return GradeResult(
                grader=self.name,
                passed=ok,
                score=1.0 if ok else 0.0,
                detail="ok" if ok else "; ".join(errors[:8]),
            )
        required = spec.params.get("required") or []
        if not isinstance(data, dict):
            ok = not required
            return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail="JSON value")
        missing = [k for k in required if k not in data]
        ok = not missing
        return GradeResult(
            grader=self.name,
            passed=ok,
            score=1.0 if ok else 0.0,
            detail="ok" if ok else f"missing keys: {missing}",
        )


class SemanticGrader(Grader):
    name = "semantic"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        expected = record.expected or str(spec.params.get("expected") or "")
        threshold = float(spec.params.get("threshold", 0.55))
        if not expected:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no expected")
        import math
        from collections import Counter

        docs = [tokenize_normalized(expected), tokenize_normalized(output.text)]
        df: Counter[str] = Counter()
        for toks in docs:
            df.update(set(toks))
        idf = {t: math.log(3 / (1 + c)) + 1 for t, c in df.items()}

        def vec(toks: list[str]) -> dict[str, float]:
            tf = Counter(toks)
            n = max(len(toks), 1)
            return {t: (c / n) * idf.get(t, 0.0) for t, c in tf.items()}

        score = cosine(vec(docs[0]), vec(docs[1]))
        return GradeResult(
            grader=self.name,
            passed=score >= threshold,
            score=round(score, 4),
            detail=f"local cosine {score:.3f} (threshold {threshold})",
        )


class LLMJudgeGrader(Grader):
    name = "llm_judge"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        path = spec.params.get("callable") or spec.params.get("import_path")
        if path:
            return CustomGrader().grade(record, output, spec)
        return GradeResult(
            grader=self.name,
            passed=None,
            skipped=True,
            detail="LLM judge is opt-in; no provider configured. Register a grader or set params.callable.",
        )


class ToolCallGrader(Grader):
    name = "tool_call"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        required = spec.params.get("required")
        forbidden = spec.params.get("forbidden") or []
        names = [c.name for c in output.tool_calls]
        required_list = required if isinstance(required, list) else ([required] if required else [])
        missing = [n for n in required_list if n not in names]
        if missing:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing tools {missing}")
        hit = [n for n in names if n in forbidden]
        if hit:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"forbidden tools: {hit}")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="tool constraints ok")


class ToolArgsGrader(Grader):
    name = "tool_args"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        constraints = spec.params.get("constraints") or []
        by_name = {c.name: c for c in output.tool_calls}
        for rule in constraints:
            name = str(rule.get("name") or "")
            call = by_name.get(name)
            if call is None:
                return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing tool {name}")
            args = call.arguments or {}
            for key in rule.get("required_args") or []:
                if key not in args:
                    return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"{name} missing arg {key}")
            equals = rule.get("equals") or {}
            for key, value in equals.items():
                if args.get(key) != value:
                    return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"{name}.{key} mismatch")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="tool args ok")


def _lcs_len(left: list[str], right: list[str]) -> int:
    if not left or not right:
        return 0
    prev = [0] * (len(right) + 1)
    for a in left:
        cur = [0]
        for j, b in enumerate(right):
            cur.append(prev[j + 1] + 1 if a == b else max(prev[j + 1], cur[-1]))
        prev = cur
    return prev[-1]


class TrajectoryGrader(Grader):
    name = "trajectory"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        max_steps = spec.params.get("max_steps")
        order = spec.params.get("order") or []
        kinds = [s.kind for s in output.trajectory] or [c.name for c in output.tool_calls]
        if max_steps is not None and len(kinds) > int(max_steps):
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"too many steps ({len(kinds)})")
        mode = str(spec.params.get("mode") or "subsequence")
        if mode == "strict" and order:
            ok = kinds == list(order)
            return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail="strict trajectory")
        if mode == "lcs" and order:
            lcs = _lcs_len([str(x) for x in order], [str(x) for x in kinds])
            denom = max(len(order), 1)
            score = lcs / denom
            threshold = float(spec.params.get("threshold", 1.0))
            ok = score >= threshold
            return GradeResult(grader=self.name, passed=ok, score=round(score, 4), detail=f"LCS {lcs}/{denom}")
        pos = 0
        for item in order:
            try:
                pos = kinds.index(item, pos) + 1
            except ValueError:
                return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing step {item}")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="trajectory ok")


class LatencyGrader(Grader):
    name = "latency"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = float(spec.params.get("max_ms", 30_000))
        latency = output.usage.latency_ms
        if latency is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no latency recorded")
        ok = latency <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{latency}ms <= {limit}ms")


class TTFTGrader(Grader):
    name = "ttft"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = float(spec.params.get("max_ms", 5_000))
        ttft = output.usage.ttft_ms
        if ttft is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no TTFT recorded")
        ok = ttft <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{ttft}ms <= {limit}ms")


class TokenGrader(Grader):
    name = "tokens"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = int(spec.params.get("max_tokens", 8_000))
        total = output.usage.total_tokens
        if total is None:
            inp = output.usage.input_tokens or 0
            out = output.usage.output_tokens or 0
            has_parts = output.usage.input_tokens is not None or output.usage.output_tokens is not None
            total = inp + out if has_parts else None
        if total is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no token usage recorded")
        ok = total <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{total} <= {limit} tokens")


class CostGrader(Grader):
    name = "cost"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = float(spec.params.get("max_usd", 1.0))
        cost = output.usage.cost_usd
        if cost is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no cost recorded")
        ok = cost <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"${cost} <= ${limit}")


def _parse_number(text: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _json_path(data: Any, path: str) -> Any:
    cur = data
    raw = path[1:] if path.startswith("$") else path
    raw = raw.lstrip(".")
    if not raw:
        return cur
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", raw)
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if not isinstance(cur, list) or idx >= len(cur):
                raise KeyError(path)
            cur = cur[idx]
        else:
            if not isinstance(cur, dict) or part not in cur:
                raise KeyError(path)
            cur = cur[part]
    return cur


class NumericToleranceGrader(Grader):
    name = "numeric_tolerance"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        expected = _parse_number(str(spec.params.get("expected") or record.expected or ""))
        actual = _parse_number(output.text)
        if expected is None or actual is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no numeric values")
        abs_tol = float(spec.params.get("abs", spec.params.get("abs_tol", 1e-6)))
        rel_tol = float(spec.params.get("rel", spec.params.get("rel_tol", 0.0)))
        ok = abs(actual - expected) <= abs_tol + rel_tol * abs(expected)
        return GradeResult(
            grader=self.name,
            passed=ok,
            score=1.0 if ok else 0.0,
            detail=f"{actual} vs {expected} (abs={abs_tol}, rel={rel_tol})",
        )


class SetEqualityGrader(Grader):
    name = "set_equality"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        try:
            actual = json.loads(output.text)
        except json.JSONDecodeError:
            actual = [x.strip() for x in output.text.split(",") if x.strip()]
        expected = spec.params.get("expected")
        if expected is None and record.expected:
            try:
                expected = json.loads(record.expected)
            except json.JSONDecodeError:
                expected = [x.strip() for x in record.expected.split(",") if x.strip()]
        if not isinstance(actual, list) or not isinstance(expected, list):
            return GradeResult(grader=self.name, passed=False, score=0.0, detail="expected JSON/list values")
        ok = set(map(str, actual)) == set(map(str, expected))
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail="set equality")


class JsonPathGrader(Grader):
    name = "json_path"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        try:
            data = json.loads(output.text)
        except json.JSONDecodeError as exc:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=str(exc))
        path = str(spec.params.get("path") or "$")
        try:
            value = _json_path(data, path)
        except (KeyError, ValueError, TypeError):
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing path {path}")
        if "equals" in spec.params:
            ok = value == spec.params["equals"]
            return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{path}={value!r}")
        if spec.params.get("exists"):
            return GradeResult(grader=self.name, passed=True, score=1.0, detail=f"{path} exists")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail=f"{path}={value!r}")


class OrderedSubsequenceGrader(Grader):
    name = "ordered_subsequence"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        order = [str(x) for x in (spec.params.get("order") or [])]
        kinds = [s.kind for s in output.trajectory] or [c.name for c in output.tool_calls]
        pos = 0
        for item in order:
            try:
                pos = kinds.index(item, pos) + 1
            except ValueError:
                return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing step {item}")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="ordered subsequence ok")


class ForbiddenToolGrader(Grader):
    name = "forbidden_tool"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        forbidden = spec.params.get("forbidden") or spec.params.get("tools") or []
        clone = GraderSpec(type="tool_call", params={"forbidden": forbidden})
        result = ToolCallGrader().grade(record, output, clone)
        return result.model_copy(update={"grader": self.name})


class RequiredToolGrader(Grader):
    name = "required_tool"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        required = spec.params.get("required") or spec.params.get("tools") or []
        clone = GraderSpec(type="tool_call", params={"required": required})
        result = ToolCallGrader().grade(record, output, clone)
        return result.model_copy(update={"grader": self.name})


class MaxToolCallsGrader(Grader):
    name = "max_tool_calls"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = int(spec.params.get("max", spec.params.get("n", 8)))
        n = len(output.tool_calls)
        ok = n <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{n} <= {limit} tool calls")


class MaxTrajectoryLengthGrader(Grader):
    name = "max_trajectory_length"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = int(spec.params.get("max", spec.params.get("n", 20)))
        n = len(output.trajectory) or len(output.tool_calls)
        ok = n <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"{n} <= {limit} steps")


class StatePredicateGrader(Grader):
    name = "state_predicate"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        expected = spec.params.get("equals") or spec.params.get("state") or {}
        actual = {}
        if isinstance(record.metadata.get("state"), dict):
            actual.update(record.metadata["state"])
        if output.trajectory:
            last = output.trajectory[-1].payload
            if isinstance(last, dict):
                actual.update(last)
        missing = [k for k, v in expected.items() if actual.get(k) != v]
        ok = not missing
        return GradeResult(
            grader=self.name,
            passed=ok,
            score=1.0 if ok else 0.0,
            detail="state ok" if ok else f"state mismatch {missing}",
        )


class LCSTrajectoryGrader(TrajectoryGrader):
    name = "lcs_trajectory"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        params = {**spec.params, "mode": spec.params.get("mode", "lcs")}
        result = super().grade(record, output, spec.model_copy(update={"params": params}))
        return result.model_copy(update={"grader": self.name})


class StrictTrajectoryGrader(TrajectoryGrader):
    name = "strict_trajectory"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        params = {**spec.params, "mode": "strict"}
        result = super().grade(record, output, spec.model_copy(update={"params": params}))
        return result.model_copy(update={"grader": self.name})


class JsonSchemaAliasGrader(JsonSchemaGrader):
    name = "json_schema"


class CustomGrader(Grader):
    name = "custom"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        path = str(spec.params.get("callable") or spec.params.get("import_path") or "")
        if not path or ":" not in path:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail="custom grader needs module:function")
        mod_name, fn_name = path.rsplit(":", 1)
        try:
            fn = getattr(importlib.import_module(mod_name), fn_name)
            result = fn(record, output, spec)
        except Exception as exc:  # noqa: BLE001
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"custom grader error: {exc}")
        if isinstance(result, GradeResult):
            return result
        if isinstance(result, dict):
            return GradeResult(grader=self.name, **result)
        ok = bool(result)
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail="custom")


for _cls, _aliases in (
    (ExactMatchGrader, ()),
    (ContainsGrader, ()),
    (NotContainsGrader, ()),
    (RegexGrader, ()),
    (JsonSchemaGrader, ()),
    (JsonSchemaAliasGrader, ()),
    (SemanticGrader, ()),
    (LLMJudgeGrader, ()),
    (ToolCallGrader, ()),
    (ToolArgsGrader, ()),
    (TrajectoryGrader, ()),
    (LCSTrajectoryGrader, ()),
    (StrictTrajectoryGrader, ()),
    (LatencyGrader, ()),
    (TTFTGrader, ()),
    (TokenGrader, ()),
    (CostGrader, ()),
    (CustomGrader, ()),
    (NumericToleranceGrader, ("numeric",)),
    (SetEqualityGrader, ("list_equality",)),
    (JsonPathGrader, ()),
    (OrderedSubsequenceGrader, ()),
    (ForbiddenToolGrader, ("forbidden_action",)),
    (RequiredToolGrader, ("required_action",)),
    (MaxToolCallsGrader, ()),
    (MaxTrajectoryLengthGrader, ()),
    (StatePredicateGrader, ()),
):
    register_grader(_cls, aliases=_aliases)


def grade_record(record: EvaluationRecord, output: AgentOutput) -> list[GradeResult]:
    specs = record.graders or [GraderSpec(type="contains")]
    results: list[GradeResult] = []
    for spec in specs:
        cls = REGISTRY.get(spec.type)
        if cls is None:
            results.append(GradeResult(grader=spec.type, passed=False, score=0.0, detail="unknown grader"))
            continue
        results.append(cls().grade(record, output, spec))
    return results


def overall_pass(grades: list[GradeResult]) -> bool | None:
    decided = [g for g in grades if not g.skipped]
    if not decided:
        return None
    return all(g.passed for g in decided)


def listed_graders() -> list[str]:
    return sorted(set(REGISTRY))
