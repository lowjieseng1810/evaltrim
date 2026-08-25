"""evaltrim doctor — local environment checks. PASS / WARN / FAIL."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from evaltrim import __version__
from evaltrim.embeddings import cache_dir, load_encoder
from evaltrim.evaluation.graders import listed_graders
from evaltrim.sandbox import LocalSandbox
from evaltrim.store import connect, default_db_path


def doctor(*, config_path: Path | None = None) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add("python", "PASS" if sys.version_info >= (3, 11) else "FAIL", ".".join(map(str, sys.version_info[:3])))
    add("package", "PASS", f"evaltrim {__version__}")

    extras = []
    for mod in ("yaml", "pydantic", "typer", "rich"):
        try:
            __import__(mod)
            extras.append(mod)
        except ImportError:
            add("dependency_" + mod, "FAIL", "missing — install with pip install evaltrim")
    add("core_dependencies", "PASS" if len(extras) == 4 else "FAIL", ", ".join(extras))

    for mod, label in (("pytest", "dev"), ("ruff", "dev"), ("mypy", "dev")):
        try:
            __import__(mod)
            add(f"optional_{label}_{mod}", "PASS", "available")
        except ImportError:
            add(f"optional_{label}_{mod}", "WARN", f"not installed (pip install evaltrim[{label}] or extra '{mod}')")

    add("graders", "PASS", f"{len(listed_graders())} registered types")

    enc = load_encoder(enabled=False)
    add("default_embeddings", "PASS", "disabled (zero network); tier-2 hashing is local")
    if os.environ.get("EVALTRIM_EMBEDDINGS"):
        enc2 = load_encoder(enabled=True)
        add("embedding_availability", "PASS" if enc2 else "WARN", enc2.name if enc2 else "unavailable")
    else:
        add("embedding_availability", "WARN", "tier 3 off; set EVALTRIM_EMBEDDINGS=1 for hashing encoder mix-in")
    if os.environ.get("EVALTRIM_LLM"):
        add("optional_llm", "WARN", "EVALTRIM_LLM is set; LLM calls may use the network")
    else:
        add("optional_llm", "PASS", "disabled")

    cfg = config_path or Path("evaltrim.yaml")
    if cfg.exists():
        add("configuration", "PASS", str(cfg.resolve()))
    else:
        examples = Path("examples/evaltrim.yaml")
        add(
            "configuration",
            "WARN",
            f"no {cfg} in cwd" + (f"; example at {examples}" if examples.exists() else ""),
        )

    try:
        cdir = cache_dir()
        cdir.mkdir(parents=True, exist_ok=True)
        add("cache", "PASS", str(cdir))
    except OSError as exc:
        add("cache", "FAIL", str(exc))

    db = default_db_path()
    try:
        conn = connect(db)
        conn.execute("SELECT 1")
        conn.close()
        add("database", "PASS", str(db))
    except (OSError, sqlite3.Error) as exc:
        add("database", "FAIL", str(exc))

    gh = os.environ.get("GITHUB_ACTIONS")
    add(
        "github_integration",
        "PASS" if gh else "WARN",
        "GITHUB_ACTIONS=true" if gh else "not running inside GitHub Actions (optional)",
    )

    try:
        box = LocalSandbox(root=Path.cwd(), timeout=1.0)
        box.resolve(".")
        add("sandbox_availability", "PASS", f"{box.kind} (not a VM)")
    except OSError as exc:
        add("sandbox_availability", "FAIL", str(exc))

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
        "first_run": ["pip install -e .", "evaltrim init", "evaltrim analyze evals.yaml", "evaltrim doctor"],
        "network": {
            "default": "no network",
            "optional_embeddings": "local hashing encoder only unless a future provider is configured",
            "optional_llm": "only if llm_enabled or EVALTRIM_LLM",
            "command_adapter": "user-supplied process; EvalTrim does not interpolate suite text into a shell",
            "sandbox": "LOCAL_SANDBOX, not a SECURE ISOLATED VM",
        },
    }
