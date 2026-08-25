"""Local SQLite persistence. No server. Reset by deleting the file."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaltrim.errors import InternalError

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  suite_hash TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    override = os.environ.get("EVALTRIM_DB")
    if override:
        return Path(override)
    return Path.cwd() / ".evaltrim" / "evaltrim.sqlite"


def connect(path: Path | None = None) -> sqlite3.Connection:
    dest = path or default_db_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(dest))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("schema", "1"),
        )
        conn.commit()
        return conn
    except sqlite3.Error as exc:
        raise InternalError(f"Local store could not be opened ({dest}): {exc}") from exc


def reset_store(path: Path | None = None) -> Path:
    dest = path or default_db_path()
    if dest.exists():
        dest.unlink()
    wal = Path(str(dest) + "-wal")
    shm = Path(str(dest) + "-shm")
    if wal.exists():
        wal.unlink()
    if shm.exists():
        shm.unlink()
    connect(dest).close()
    return dest


def put_kv(kind: str, key: str, value: Any, *, path: Path | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO kv(key, value, kind, created_at) VALUES (?, ?, ?, ?)",
            (key, json.dumps(value), kind, datetime.now(UTC).isoformat()),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise InternalError(f"Local store write failed: {exc}") from exc
    finally:
        conn.close()


def get_kv(key: str, *, path: Path | None = None) -> Any | None:
    conn = connect(path)
    try:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise InternalError(f"Local store read failed or cache is corrupt: {exc}") from exc
    finally:
        conn.close()


def append_history(kind: str, payload: Any, *, suite_hash: str | None = None, path: Path | None = None) -> None:
    conn = connect(path)
    try:
        conn.execute(
            "INSERT INTO history(kind, suite_hash, payload, created_at) VALUES (?, ?, ?, ?)",
            (kind, suite_hash, json.dumps(payload), datetime.now(UTC).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def recent_history(kind: str | None = None, *, limit: int = 10, path: Path | None = None) -> list[dict[str, Any]]:
    conn = connect(path)
    try:
        if kind:
            rows = conn.execute(
                "SELECT kind, suite_hash, payload, created_at FROM history WHERE kind = ? ORDER BY id DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT kind, suite_hash, payload, created_at FROM history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for kind_v, suite_hash, payload, created in rows:
            out.append(
                {
                    "kind": kind_v,
                    "suite_hash": suite_hash,
                    "payload": json.loads(payload),
                    "created_at": created,
                }
            )
        return out
    except (sqlite3.Error, json.JSONDecodeError):
        return []
    finally:
        conn.close()
