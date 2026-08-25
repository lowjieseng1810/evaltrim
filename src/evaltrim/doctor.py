"""evaltrim doctor — local environment checks. PASS / WARN / FAIL."""

from __future__ import annotations

import os
import sqlite3
import sys
from typing import Any

from evaltrim import __version__
from evaltrim.embeddings import cache_dir, load_encoder
from evaltrim.store import connect, default_db_path


def doctor() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add("package_version", "PASS", __version__)
    add("python_version", "PASS" if sys.version_info >= (3, 11) else "FAIL", ".".join(map(str, sys.version_info[:3])))

    extras = []
    for mod in ("yaml", "pydantic", "typer", "rich"):
        try:
            __import__(mod)
            extras.append(mod)
        except ImportError:
            add("dependency_" + mod, "FAIL", "missing")
    add("core_dependencies", "PASS" if len(extras) == 4 else "FAIL", ", ".join(extras))

    enc = load_encoder(enabled=False)
    add("default_embeddings", "PASS", "disabled (zero network)")
    if os.environ.get("EVALTRIM_EMBEDDINGS"):
        enc2 = load_encoder(enabled=True)
        add("optional_embeddings", "PASS" if enc2 else "WARN", enc2.name if enc2 else "unavailable")
    else:
        add("optional_embeddings", "WARN", "not enabled; set EVALTRIM_EMBEDDINGS=1 for hashing encoder")
    if os.environ.get("EVALTRIM_LLM"):
        add("optional_llm", "WARN", "EVALTRIM_LLM is set; LLM calls may use the network")
    else:
        add("optional_llm", "PASS", "disabled")

    try:
        cdir = cache_dir()
        cdir.mkdir(parents=True, exist_ok=True)
        add("cache_dir", "PASS", str(cdir))
    except OSError as exc:
        add("cache_dir", "FAIL", str(exc))

    db = default_db_path()
    try:
        conn = connect(db)
        conn.execute("SELECT 1")
        conn.close()
        add("storage", "PASS", str(db))
    except (OSError, sqlite3.Error) as exc:
        add("storage", "FAIL", str(exc))

    gh = os.environ.get("GITHUB_ACTIONS")
    add(
        "github_integration",
        "PASS" if gh else "WARN",
        "GITHUB_ACTIONS=true" if gh else "not running inside GitHub Actions",
    )

    if enc is not None:
        add("encoder_loaded_by_default", "WARN", "unexpected default encoder")

    worst = "PASS"
    if any(c["status"] == "FAIL" for c in checks):
        worst = "FAIL"
    elif any(c["status"] == "WARN" for c in checks):
        worst = "WARN"
    return {
        "overall": worst,
        "checks": checks,
        "network": {
            "default": "no network",
            "optional_embeddings": "local hashing encoder only unless a future provider is configured",
            "optional_llm": "only if llm_enabled or EVALTRIM_LLM",
            "command_adapter": "user-supplied process; EvalTrim does not interpolate suite text into a shell",
        },
    }
