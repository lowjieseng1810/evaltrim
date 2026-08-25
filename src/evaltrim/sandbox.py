"""Minimal local sandbox. Not a cloud isolation platform."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class LocalSandbox:
    """Controlled subprocess + env + filesystem root + tool mocks.

    Limitations: this is not a VM, container, or seccomp jail. A hostile binary
    given to `run` can still do anything the OS user can do. Use only for trusted
    local tools and tests.
    """

    def __init__(
        self,
        *,
        root: Path | None = None,
        env: Mapping[str, str] | None = None,
        tool_mocks: Mapping[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.root = Path(root) if root else Path.cwd()
        self.env = dict(env or {})
        self.tool_mocks = dict(tool_mocks or {})
        self.timeout = timeout

    def resolve(self, path: str | Path) -> Path:
        target = (self.root / path).resolve()
        root = self.root.resolve()
        if root not in target.parents and target != root:
            raise PermissionError(f"path escapes sandbox root: {target}")
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

    def run(self, argv: list[str], *, cwd: Path | None = None) -> dict[str, Any]:
        merged = {**os.environ, **self.env}
        proc = subprocess.run(
            argv,
            cwd=str(cwd or self.root),
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=merged,
            check=False,
            shell=False,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
