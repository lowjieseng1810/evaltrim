"""Local snapshot store for analysis and run batches."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from evaltrim.models import AnalysisResult


def snapshot_dir(root: Path | None = None) -> Path:
    base = root or Path.cwd() / ".evaltrim" / "snapshots"
    base.mkdir(parents=True, exist_ok=True)
    return base


def save_analysis(name: str, result: AnalysisResult, *, root: Path | None = None) -> Path:
    path = snapshot_dir(root) / f"{name}.json"
    payload = {
        "name": name,
        "kind": "analysis",
        "saved_at": datetime.now(UTC).isoformat(),
        "result": json.loads(result.model_dump_json()),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_analysis(name: str, *, root: Path | None = None) -> AnalysisResult:
    path = snapshot_dir(root) / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return AnalysisResult.model_validate(data["result"])


def list_snapshots(root: Path | None = None) -> list[str]:
    return sorted(p.stem for p in snapshot_dir(root).glob("*.json"))
