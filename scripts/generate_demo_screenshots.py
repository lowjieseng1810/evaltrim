"""Capture real CLI output into docs/images. No fabricated numbers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
ASSETS = ROOT / "docs" / "assets"


def text_to_svg(text: str, title: str, dest: Path, *, width: int = 920) -> None:
    lines = text.rstrip().splitlines() or [""]
    lines = lines[:48]
    height = 48 + 18 * len(lines) + 28
    body = []
    y = 56
    for line in lines:
        body.append(
            f'<text x="24" y="{y}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="13" fill="#e7ecf3">{escape(line[:120])}</text>'
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


def run_cli(args: list[str]) -> str:
    env = {**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONPATH": str(ROOT / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "evaltrim.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return out


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
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
        (IMAGES / name).write_text(text, encoding="utf-8")
        svg_name = name.replace(".txt", ".svg")
        text_to_svg(text, title, IMAGES / svg_name)
        print("wrote", svg_name)

    html = run_cli(["analyze", demo, "--format", "html"])
    (IMAGES / "report.html").write_text(html, encoding="utf-8")
    print("wrote report.html")

    # Combined removal screenshot: KEEP then SAFE
    combo = (IMAGES / "removal-keep.txt").read_text(encoding="utf-8")
    combo += "\n---\n"
    combo += (IMAGES / "removal-safe.txt").read_text(encoding="utf-8")
    text_to_svg(combo, "Removal simulation KEEP vs SAFE_TO_RETIRE", IMAGES / "removal-simulation.svg")
    text_to_svg(
        (IMAGES / "unique-witness.txt").read_text(encoding="utf-8"),
        "Unique witness / why KEEP",
        IMAGES / "unique-witness.svg",
    )
    text_to_svg((IMAGES / "cli-analyze.txt").read_text(encoding="utf-8"), "evaltrim analyze", IMAGES / "cli-main.svg")
    text_to_svg((IMAGES / "github-pr.txt").read_text(encoding="utf-8"), "GitHub PR comment", IMAGES / "github-pr-comment.svg")
    text_to_svg((IMAGES / "suite-health.txt").read_text(encoding="utf-8"), "evaltrim health", IMAGES / "suite-health.svg")
    text_to_svg((IMAGES / "evaluation-debt.txt").read_text(encoding="utf-8"), "evaltrim debt", IMAGES / "evaluation-debt.svg")
    text_to_svg((IMAGES / "regression.txt").read_text(encoding="utf-8"), "evaltrim compare", IMAGES / "regression.svg")

    # Keep legacy assets in sync
    ASSETS.mkdir(parents=True, exist_ok=True)
    for src in IMAGES.glob("*.svg"):
        (ASSETS / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (ASSETS / "report.html").write_text((IMAGES / "report.html").read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
