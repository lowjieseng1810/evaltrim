"""Batch / multi-run evaluation against a local adapter."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from hashlib import sha256
from time import perf_counter

from evaltrim.core.manifest import AgentOutput, EvaluationRecord, GradeResult
from evaltrim.evaluation.graders import grade_record, overall_pass
from evaltrim.evaluation.statistics import summarize_runs
from evaltrim.models import TestSuite
from evaltrim.runtime.adapters import AgentAdapter, EchoExpectedAdapter


@dataclass
class CaseRun:
    record_id: str
    output: AgentOutput
    grades: list[GradeResult]
    passed: bool | None
    fingerprint: str


@dataclass
class BatchResult:
    cases: list[CaseRun] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    adapter: str = ""
    dry_run: bool = False
    repeats: int = 1
    runtime_seconds: float = 0.0


def fingerprint(record: EvaluationRecord, output: AgentOutput) -> str:
    raw = f"{record.id}|{record.input}|{output.text}|{output.model}|{output.provider}"
    return sha256(raw.encode()).hexdigest()[:16]


def run_record(record: EvaluationRecord, adapter: AgentAdapter) -> CaseRun:
    output = adapter.run(record)
    grades = grade_record(record, output)
    record.output = output
    record.grades = grades
    return CaseRun(
        record_id=record.id,
        output=output,
        grades=grades,
        passed=overall_pass(grades),
        fingerprint=fingerprint(record, output),
    )


def run_suite(
    suite: TestSuite,
    *,
    adapter: AgentAdapter | None = None,
    repeats: int = 1,
    workers: int = 1,
    dry_run: bool = False,
    smoke: int | None = None,
) -> BatchResult:
    adapter = adapter or EchoExpectedAdapter()
    records = [EvaluationRecord.from_test_case(t) for t in suite.tests]
    if smoke is not None:
        records = records[: max(smoke, 0)]
    t0 = perf_counter()
    if dry_run:
        return BatchResult(
            cases=[],
            summary={"planned": [r.id for r in records], "adapter": adapter.name},
            adapter=adapter.name,
            dry_run=True,
            repeats=repeats,
            runtime_seconds=0.0,
        )

    jobs: list[EvaluationRecord] = []
    for _ in range(max(repeats, 1)):
        jobs.extend(records)

    results: list[CaseRun] = []
    if workers <= 1:
        results = [run_record(rec, adapter) for rec in jobs]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(run_record, rec, adapter) for rec in jobs]
            for fut in as_completed(futs):
                results.append(fut.result())
        results.sort(key=lambda c: c.record_id)

    flags = [bool(c.passed) for c in results if c.passed is not None]
    lats = [c.output.usage.latency_ms or 0.0 for c in results]
    return BatchResult(
        cases=results,
        summary={
            **summarize_runs(flags, lats),
            "graded": len(results),
            "unique_fingerprints": len({c.fingerprint for c in results}),
        },
        adapter=adapter.name,
        repeats=repeats,
        runtime_seconds=round(perf_counter() - t0, 6),
    )
