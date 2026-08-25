"""Render actual CLI capture files as SVG screenshots. No mock copy."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
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
    title_xml = escape(title)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#0f1419"/>
  <rect x="8" y="8" width="{width - 16}" height="{height - 16}" rx="10" fill="#161d27" stroke="#2c3a4d"/>
  <circle cx="28" cy="26" r="6" fill="#ff5f56"/>
  <circle cx="48" cy="26" r="6" fill="#ffbd2e"/>
  <circle cx="68" cy="26" r="6" fill="#27c93f"/>
  <text x="92" y="31" font-family="sans-serif" font-size="13" fill="#9db0c8">{title_xml}</text>
  {"".join(body)}
</svg>
'''
    dest.write_text(svg, encoding="utf-8")


def main() -> None:
    mapping = {
        "cli-analyze.txt": ("evaltrim analyze examples/demo_suite.yaml", "cli-evaluation-summary.svg"),
        "cli-regression.txt": ("evaltrim compare (suite snapshot diff)", "regression-comparison.svg"),
        "cli-simulate.txt": ("evaltrim simulate-remove … privacy-delete", "unique-witness-simulation.svg"),
        "cli-health.txt": ("evaltrim health examples/demo_suite.yaml", "suite-health.svg"),
        "cli-debt.txt": ("evaltrim debt examples/demo_suite.yaml", "evaluation-debt.svg"),
        "cli-github.txt": ("evaltrim analyze --format github", "github-pr-comment.svg"),
    }
    for src_name, (title, dest_name) in mapping.items():
        src = ASSETS / src_name
        text_to_svg(src.read_text(encoding="utf-8"), title, ASSETS / dest_name)
        print("wrote", dest_name)


if __name__ == "__main__":
    main()
