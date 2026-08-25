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
    (JsonSchemaGrader, ("json_schema",)),
    (SemanticGrader, ()),
    (LLMJudgeGrader, ()),
    (ToolCallGrader, ()),
    (ToolArgsGrader, ()),
    (TrajectoryGrader, ()),
    (LatencyGrader, ()),
    (TTFTGrader, ()),
    (TokenGrader, ()),
    (CostGrader, ()),
    (CustomGrader, ()),
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
