"""LOCAL SANDBOX — process/fs/env controls for trusted local tools.

This is not a SECURE ISOLATED VM. A hostile binary given to `run` can still do
anything the OS user can do. EvalTrim does not claim container, seccomp, or
hypervisor isolation.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_INHERIT_KEYS = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "COMSPEC",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
    "TMP",
    "TEMP",
    "TMPDIR",
    "PYTHONPATH",
    "VIRTUAL_ENV",
)


class LocalSandbox:
    """Controlled subprocess + env + filesystem root + tool mocks.

    Kind: LOCAL SANDBOX
    Not: SECURE ISOLATED VM
    """

    kind = "LOCAL_SANDBOX"

    def __init__(
        self,
        *,
        root: Path | None = None,
        env: Mapping[str, str] | None = None,
        tool_mocks: Mapping[str, Any] | None = None,
        timeout: float = 5.0,
        inherit_env: bool = False,
        max_output: int = 64_000,
        max_processes: int | None = 32,
        frozen_time: str | None = None,
    ) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.env = dict(env or {})
        self.tool_mocks = dict(tool_mocks or {})
        self.timeout = timeout
        self.inherit_env = inherit_env
        self.max_output = max_output
        self.max_processes = max_processes
        self.frozen_time = frozen_time

    def resolve(self, path: str | Path) -> Path:
        target = (self.root / path).resolve()
        root = self.root.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise PermissionError(f"path escapes sandbox root: {target}") from exc
        return target

    def read_text(self, path: str | Path) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_text(self, path: str | Path, content: str) -> None:
        dest = self.resolve(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    def call_tool(self, name: str, **kwargs: Any) -> Any:
        if name not in self.tool_mocks:
            raise KeyError(f"tool {name} is not mocked")
        fn = self.tool_mocks[name]
        return fn(**kwargs) if callable(fn) else fn

    def _env(self) -> dict[str, str]:
        if self.inherit_env:
            merged = {**os.environ, **self.env}
        else:
            merged = {k: v for k in _INHERIT_KEYS if (v := os.environ.get(k))}
            merged.update(self.env)
        merged["EVALTRIM_SANDBOX"] = "LOCAL_SANDBOX"
        merged["PWD"] = str(self.root)
        if self.frozen_time:
            merged["EVALTRIM_FAKE_TIME"] = self.frozen_time
        return merged

    def run(self, argv: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
        if not argv:
            raise ValueError("argv must be non-empty")
        if argv[0] in {os.environ.get("SHELL", ""), "sh", "bash", "zsh"} and len(argv) >= 2 and argv[1] == "-c":
            # Still allowed, but never interpolate suite text here. Callers pass argv.
            pass
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd or self.root),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=self._env(),
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "returncode": 124,
                "stdout": _clip(exc.stdout, self.max_output) if isinstance(exc.stdout, str) else "",
                "stderr": f"timeout after {self.timeout}s",
                "timeout": True,
                "kind": self.kind,
            }
        return {
            "returncode": proc.returncode,
            "stdout": _clip(proc.stdout, self.max_output),
            "stderr": _clip(proc.stderr, self.max_output),
            "timeout": False,
            "kind": self.kind,
        }


def _clip(text: str | None, limit: int) -> str:
    raw = text or ""
    if len(raw) <= limit:
        return raw
    return raw[:limit] + "\n...[truncated]"
