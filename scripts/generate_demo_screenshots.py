"""Capture real CLI output into docs/images. No fabricated numbers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
ASSETS = ROOT / "docs" / "assets"
LAUNCH = IMAGES / "launch"


def sanitize(text: str) -> str:
    text = text.replace(str(ROOT), ".")
    text = text.replace("/workspace", ".")
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    text = re.sub(r"x-access-token:[^@\s]+@", "", text)
    text = re.sub(r"(sk-|ghp_|github_pat_)[A-Za-z0-9._-]+", "[redacted]", text)
    return text


def crop_explain(text: str) -> str:
    """Keep the human-readable WHY KEEP block; drop the trailing dict dump."""
    marker = "\n{"
    if "{'decision'" in text:
        return text.split("{'decision'", 1)[0].rstrip()
    if marker in text:
        return text.split(marker, 1)[0].rstrip()
    return text.rstrip()


def text_to_svg(text: str, title: str, dest: Path, *, width: int = 920, max_lines: int = 36) -> None:
    lines = text.rstrip().splitlines() or [""]
    lines = lines[:max_lines]
    height = 48 + 18 * len(lines) + 28
    body = []
    y = 56
    for line in lines:
        body.append(
            f'<text x="24" y="{y}" font-family="ui-monospace, SFMono-Regular, Menlo, JetBrains Mono, monospace" '
            f'font-size="13" fill="#e7ecf3">{escape(line[:118])}</text>'
        )
        y += 18
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#0f1419"/>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="10" fill="#161d27" stroke="#2c3a4d"/>
  <circle cx="28" cy="26" r="6" fill="#ff5f56"/>
  <circle cx="48" cy="26" r="6" fill="#ffbd2e"/>
  <circle cx="68" cy="26" r="6" fill="#27c93f"/>
  <text x="92" y="31" font-family="sans-serif" font-size="13" fill="#9db0c8">{escape(title)}</text>
  {"".join(body)}
</svg>
'''
    dest.write_text(svg, encoding="utf-8")


def svg_to_png(svg: Path, png: Path, *, width: int) -> None:
    converter = shutil.which("rsvg-convert")
    if not converter:
        return
    subprocess.run(
        [converter, "-w", str(width), "-o", str(png), str(svg)],
        check=True,
    )


def run_cli(args: list[str]) -> str:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "COLUMNS": "120", "TERM": "dumb"}
    proc = subprocess.run(
        [sys.executable, "-m", "evaltrim.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return sanitize((proc.stdout or "") + (proc.stderr or ""))


def publish(svg: Path, stem: str) -> None:
    """Write numbered README + launch copies."""
    numbered = {
        "cli-main": "01-main-cli",
        "unique-witness": "02-unique-witness",
        "removal-simulation": "03-removal-simulation",
        "suite-health": "04-suite-health",
        "regression": "05-regression",
        "github-pr-comment": "06-github-pr",
    }
    alias = numbered.get(stem)
    if alias:
        (IMAGES / f"{alias}.svg").write_text(svg.read_text(encoding="utf-8"), encoding="utf-8")
        svg_to_png(svg, IMAGES / f"{alias}.png", width=920)
        svg_to_png(svg, LAUNCH / f"{alias}.png", width=1840)
    svg_to_png(svg, IMAGES / f"{stem}.png", width=920)


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    LAUNCH.mkdir(parents=True, exist_ok=True)
    demo = "examples/demo_suite.yaml"
    captures = {
        "cli-main.txt": (["status", demo], "evaltrim status"),
        "cli-analyze.txt": (["analyze", demo], "evaltrim analyze"),
        "unique-witness.txt": (["explain", "privacy-delete", "--suite", demo], "evaltrim explain privacy-delete"),
        "removal-keep.txt": (["simulate-remove", demo, "privacy-delete"], "simulate-remove unique critical"),
        "removal-safe.txt": (["simulate-remove", demo, "refund-002b"], "simulate-remove duplicate"),
        "suite-health.txt": (["health", demo], "evaltrim health"),
        "evaluation-debt.txt": (["debt", demo], "evaltrim debt"),
        "regression.txt": (["compare", demo, demo], "evaltrim compare (identical suites)"),
        "github-pr.txt": (["analyze", demo, "--format", "github"], "evaltrim analyze --format github"),
    }
    for name, (args, title) in captures.items():
        text = run_cli(args)
        if name == "unique-witness.txt":
            text = crop_explain(text)
        (IMAGES / name).write_text(text, encoding="utf-8")
        text_to_svg(text, title, IMAGES / name.replace(".txt", ".svg"))
        print("wrote", name)

    html = run_cli(["analyze", demo, "--format", "html"])
    (IMAGES / "report.html").write_text(html, encoding="utf-8")

    combo = (IMAGES / "removal-keep.txt").read_text(encoding="utf-8")
    combo += "\n---\n"
    combo += (IMAGES / "removal-safe.txt").read_text(encoding="utf-8")
    text_to_svg(combo, "evaltrim simulate-remove  KEEP vs SAFE_TO_RETIRE", IMAGES / "removal-simulation.svg")
    text_to_svg(
        (IMAGES / "unique-witness.txt").read_text(encoding="utf-8"),
        "evaltrim explain privacy-delete",
        IMAGES / "unique-witness.svg",
    )
    text_to_svg((IMAGES / "cli-analyze.txt").read_text(encoding="utf-8"), "evaltrim analyze", IMAGES / "cli-main.svg")
    text_to_svg(
        (IMAGES / "github-pr.txt").read_text(encoding="utf-8"),
        "evaltrim analyze --format github",
        IMAGES / "github-pr-comment.svg",
    )
    text_to_svg(
        (IMAGES / "suite-health.txt").read_text(encoding="utf-8"),
        "evaltrim health",
        IMAGES / "suite-health.svg",
    )
    text_to_svg(
        (IMAGES / "evaluation-debt.txt").read_text(encoding="utf-8"),
        "evaltrim debt",
        IMAGES / "evaluation-debt.svg",
    )
    text_to_svg(
        (IMAGES / "regression.txt").read_text(encoding="utf-8"),
        "evaltrim compare",
        IMAGES / "regression.svg",
    )

    for src in IMAGES.glob("*.svg"):
        (ASSETS / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        publish(src, src.stem)
    (ASSETS / "report.html").write_text((IMAGES / "report.html").read_text(encoding="utf-8"), encoding="utf-8")
    print("screenshots ready")


if __name__ == "__main__":
    main()
