"""Record / replay local agent outputs. No hosted store."""

from __future__ import annotations

import json
from pathlib import Path

from evaltrim.core.manifest import AgentOutput, EvaluationRecord
from evaltrim.evaluation.graders import grade_record, overall_pass
from evaltrim.runtime.runner import BatchResult, CaseRun, fingerprint


def save_recording(path: Path, batch: BatchResult) -> None:
    payload = {
        "adapter": batch.adapter,
        "repeats": batch.repeats,
        "cases": [
            {
                "id": c.record_id,
                "output": c.output.model_dump(mode="json"),
                "passed": c.passed,
                "fingerprint": c.fingerprint,
                "grades": [g.model_dump(mode="json") for g in c.grades],
            }
            for c in batch.cases
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_recording(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def replay_recording(path: Path, records: list[EvaluationRecord]) -> BatchResult:
    stored = {row["id"]: row for row in load_recording(path).get("cases", [])}
    cases: list[CaseRun] = []
    for rec in records:
        row = stored.get(rec.id)
        if row is None:
            continue
        output = AgentOutput.model_validate(row["output"])
        grades = grade_record(rec, output)
        cases.append(
            CaseRun(
                record_id=rec.id,
                output=output,
                grades=grades,
                passed=overall_pass(grades),
                fingerprint=fingerprint(rec, output),
            )
        )
    return BatchResult(cases=cases, adapter="replay", summary={"replayed": len(cases)})
