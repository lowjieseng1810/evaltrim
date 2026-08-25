"""Watch local files and rerun impacted evaluations. Debounced; no duplicate runs."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path

WATCH_SUFFIXES = {".yaml", ".yml", ".json", ".py", ".md", ".txt", ".toml"}
WATCH_HINTS = ("prompt", "eval", "suite", "tool", "policy", "agent", "config")


def watch_targets(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "node_modules", "__pycache__", ".evaltrim"} for part in path.parts):
            continue
        if path.suffix.lower() not in WATCH_SUFFIXES:
            continue
        name = path.name.lower()
        if path.suffix.lower() in {".yaml", ".yml", ".json"} or any(h in name for h in WATCH_HINTS):
            files.append(path)
    return sorted(files)


def snapshot_mtimes(paths: Iterable[Path]) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in paths:
        try:
            out[str(path)] = path.stat().st_mtime
        except OSError:
            continue
    return out


def changed_since(prev: dict[str, float], current: dict[str, float]) -> list[str]:
    changed = []
    for key, mtime in current.items():
        if key not in prev or mtime > prev[key] + 1e-9:
            changed.append(key)
    for key in prev:
        if key not in current:
            changed.append(key)
    return sorted(set(changed))


def debounce(events: list[str], *, window_s: float, last_fire: float, now: float) -> tuple[list[str], bool]:
    if not events:
        return [], False
    if now - last_fire < window_s:
        return events, False
    return events, True


def watch_once(
    root: Path,
    prev: dict[str, float] | None = None,
    *,
    debounce_s: float = 0.4,
    on_change: Callable[[list[str]], None] | None = None,
) -> dict[str, float]:
    targets = watch_targets(root)
    current = snapshot_mtimes(targets)
    if prev is None:
        return current
    events = changed_since(prev, current)
    _, fire = debounce(events, window_s=debounce_s, last_fire=0.0, now=debounce_s + 1.0)
    if fire and events and on_change:
        on_change(events)
    return current


def watch_loop(
    root: Path,
    *,
    debounce_s: float = 0.75,
    interval_s: float = 0.5,
    once: bool = False,
    on_change: Callable[[list[str]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    prev = watch_once(root)
    last_fire = 0.0
    pending: list[str] = []
    if once:
        return
    while True:
        if should_stop and should_stop():
            return
        time.sleep(interval_s)
        current = snapshot_mtimes(watch_targets(root))
        pending.extend(changed_since(prev, current))
        prev = current
        now = time.monotonic()
        events, fire = debounce(sorted(set(pending)), window_s=debounce_s, last_fire=last_fire, now=now)
        if fire and events:
            last_fire = now
            pending = []
            if on_change:
                on_change(events)
