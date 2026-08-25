"""Modular graders. Default path is local and deterministic."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult, GraderSpec
from evaltrim.similarity import cosine, tokenize_normalized


class Grader(ABC):
    name = "base"

    @abstractmethod
    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        raise NotImplementedError


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


class RegexGrader(Grader):
    name = "regex"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        pattern = str(spec.params.get("pattern") or record.expected or "")
        try:
            ok = re.search(pattern, output.text, flags=re.IGNORECASE) is not None
        except re.error as exc:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"invalid regex: {exc}")
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=pattern)


class JsonSchemaGrader(Grader):
    name = "json"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        try:
            data = json.loads(output.text)
        except json.JSONDecodeError as exc:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=str(exc))
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
        # Local TF-IDF-like cosine on normalized tokens (closed two-doc corpus).
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
        return GradeResult(
            grader=self.name,
            passed=None,
            skipped=True,
            detail="LLM judge is opt-in; no provider configured. Set a Grader implementation to enable.",
        )


class ToolCallGrader(Grader):
    name = "tool_call"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        required = spec.params.get("required")
        forbidden = spec.params.get("forbidden") or []
        names = [c.name for c in output.tool_calls]
        if required and required not in names:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"missing tool {required}")
        hit = [n for n in names if n in forbidden]
        if hit:
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"forbidden tools: {hit}")
        return GradeResult(grader=self.name, passed=True, score=1.0, detail="tool constraints ok")


class TrajectoryGrader(Grader):
    name = "trajectory"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        max_steps = spec.params.get("max_steps")
        order = spec.params.get("order") or []
        kinds = [s.kind for s in output.trajectory] or [c.name for c in output.tool_calls]
        if max_steps is not None and len(kinds) > int(max_steps):
            return GradeResult(grader=self.name, passed=False, score=0.0, detail=f"too many steps ({len(kinds)})")
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


class CostGrader(Grader):
    name = "cost"

    def grade(self, record: EvaluationRecord, output: AgentOutput, spec: GraderSpec) -> GradeResult:
        limit = float(spec.params.get("max_usd", 1.0))
        cost = output.usage.cost_usd
        if cost is None:
            return GradeResult(grader=self.name, passed=None, skipped=True, detail="no cost recorded")
        ok = cost <= limit
        return GradeResult(grader=self.name, passed=ok, score=1.0 if ok else 0.0, detail=f"${cost} <= ${limit}")


REGISTRY: dict[str, type[Grader]] = {
    g.name: g
    for g in (
        ExactMatchGrader,
        ContainsGrader,
        RegexGrader,
        JsonSchemaGrader,
        SemanticGrader,
        LLMJudgeGrader,
        ToolCallGrader,
        TrajectoryGrader,
        LatencyGrader,
        CostGrader,
    )
}


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
