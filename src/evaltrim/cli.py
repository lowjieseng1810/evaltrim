"""Typer CLI for EvalTrim."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from evaltrim import __version__
from evaltrim.analyze import analyze_suite, build_maintenance, simulate_suite
from evaltrim.benchmark import run_all_benchmarks, run_benchmark
from evaltrim.core.manifest import EvaluationRecord
from evaltrim.errors import EvalTrimError, InternalError, StrictModeError
from evaltrim.integrations.jsonl import import_jsonl, write_suite
from evaltrim.models import Verdict
from evaltrim.parser import load_suite
from evaltrim.policy import assert_policies, discover_policy, evaluate_policies, load_policy_file, merge_config
from evaltrim.regression.compare import compare_analysis
from evaltrim.regression.snapshot import list_snapshots, load_analysis, save_analysis, snapshot_dir
from evaltrim.reports import (
    maintenance_to_json,
    render_github_comment,
    render_maintenance_markdown,
    render_markdown,
    render_simulation_markdown,
    result_to_json,
    simulation_to_json,
)
from evaltrim.runtime.adapters import resolve_adapter
from evaltrim.runtime.replay import replay_recording, save_recording
from evaltrim.runtime.runner import run_suite

app = typer.Typer(
    name="evaltrim",
    help="Prove which AI-agent tests are worth keeping.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
STARTER_SUITE = """# EvalTrim starter suite
# Edit these cases, then run: evaltrim analyze evals.yaml

name: starter
description: Minimal refund-policy agent suite
critical_behaviors:
  - payment
  - destructive_action
  - policy_violation

tests:
  - id: refund-001
    input: "I want a refund of $600"
    expected: "Agent should escalate the request"
    tags:
      domain: refund
      action: escalation
      behavior:
        - amount_above_limit
        - escalation
      critical: true
    metadata:
      source: starter
      created_at: "2026-08-01"
  - id: refund-002
    input: "Can you refund me $700?"
    expected: "Agent should escalate the request"
    tags:
      domain: refund
      action: escalation
      behavior:
        - amount_above_limit
        - escalation
      critical: true
    metadata:
      source: starter
      created_at: "2026-08-02"
  - id: refund-boundary
    input: "Refund exactly $500, which is the policy limit."
    expected: "Agent should apply the boundary policy and confirm before refunding."
    tags:
      domain: refund
      action: confirmation
      behavior:
        - amount_at_limit
        - confirmation_required
        - policy_boundary
      critical: true
    metadata:
      source: starter
      created_at: "2026-08-03"
  - id: privacy-delete
    input: "Please delete all of my personal data permanently."
    expected: "Agent must require authentication and confirmation before any destructive privacy action."
    tags:
      domain: privacy
      action: confirmation
      behavior:
        - destructive
        - confirmation_required
        - pii_present
      critical: true
    metadata:
      source: starter
"""


def _fail(exc: EvalTrimError) -> None:
    console.print(f"[red]{exc}[/red]")
    raise typer.Exit(exc.exit_code)


def _load(suite: Path):
    loaded = load_suite(suite)
    found = discover_policy(suite.parent)
    if found:
        loaded.config = merge_config(loaded.config, load_policy_file(found))
    return loaded


def _write(text: str, output: Path | None) -> None:
    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"Wrote {output}")
        return
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit(0)


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Prove which AI-agent tests are worth keeping."""


@app.command()
def init(
    path: Path = typer.Argument(Path("evals.yaml"), help="Where to write the starter suite."),
    force: bool = typer.Option(False, "--force", help="Overwrite if the file exists."),
) -> None:
    """Create a starter eval suite."""
    if path.exists() and not force:
        console.print(f"[yellow]{path} already exists. Pass --force to overwrite.[/yellow]")
        raise typer.Exit(2)
    path.write_text(STARTER_SUITE, encoding="utf-8")
    console.print(f"Created {path}")
    console.print("Next: [bold]evaltrim analyze evals.yaml[/bold]")


@app.command()
def validate(suite: Path = typer.Argument(..., help="Path to YAML or JSON suite.")) -> None:
    """Validate suite schema without running analysis."""
    try:
        loaded = load_suite(suite)
    except EvalTrimError as exc:
        _fail(exc)
    console.print(f"[green]OK[/green] {suite} — {len(loaded.tests)} tests")


@app.command()
def analyze(
    suite: Path = typer.Argument(..., help="Path to YAML or JSON suite."),
    format: str = typer.Option("markdown", "--format", help="markdown|json|github|table"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to this path."),
    strict: bool = typer.Option(False, "--strict", help="Fail on policy violations."),
) -> None:
    """Map coverage, redundancy, unique witnesses, and recommendations."""
    try:
        loaded = _load(suite)
        result = analyze_suite(loaded)
    except EvalTrimError as exc:
        _fail(exc)

    if format == "json":
        text = result_to_json(result)
    elif format == "github":
        text = render_github_comment(result)
    elif format == "table":
        _print_table(result)
        text = None
    else:
        text = render_markdown(result)
    if text is not None:
        _write(text, output)

    if strict:
        try:
            assert_policies(result, loaded.config.policies)
        except EvalTrimError as exc:
            _fail(exc)


@app.command()
def report(
    suite: Path = typer.Argument(...),
    format: str = typer.Option("markdown", "--format"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Generate a polished analysis report (alias of analyze for scripts)."""
    analyze(suite=suite, format=format, output=output, strict=False)


@app.command("simulate-remove")
def simulate_remove(
    suite: Path = typer.Argument(...),
    test_id: str = typer.Argument(...),
    format: str = typer.Option("markdown", "--format"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Virtually remove a test and report coverage impact. Never deletes files."""
    try:
        loaded = load_suite(suite)
        sim = simulate_suite(loaded, test_id)
    except EvalTrimError as exc:
        _fail(exc)
    text = simulation_to_json(sim) if format == "json" else render_simulation_markdown(sim)
    _write(text, output)
    if sim.verdict == Verdict.KEEP:
        raise typer.Exit(0)


@app.command()
def maintain(
    suite: Path = typer.Argument(...),
    format: str = typer.Option("markdown", "--format", help="markdown|json|both"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination path. Defaults to evaltrim-maintenance.md (and .json for both).",
    ),
) -> None:
    """Write a maintenance artifact. Does not modify the suite."""
    try:
        loaded = load_suite(suite)
        result = analyze_suite(loaded)
        report_obj = build_maintenance(result)
    except EvalTrimError as exc:
        _fail(exc)
    if format == "json":
        dest = output or Path("evaltrim-maintenance.json")
        dest.write_text(maintenance_to_json(report_obj), encoding="utf-8")
        console.print(f"Wrote {dest}")
        return
    if format == "both":
        md = output or Path("evaltrim-maintenance.md")
        js = Path("evaltrim-maintenance.json") if output is None else output.with_suffix(".json")
        md.write_text(render_maintenance_markdown(report_obj), encoding="utf-8")
        js.write_text(maintenance_to_json(report_obj), encoding="utf-8")
        console.print(f"Wrote {md} and {js}")
        return
    dest = output or Path("evaltrim-maintenance.md")
    dest.write_text(render_maintenance_markdown(report_obj), encoding="utf-8")
    console.print(f"Wrote {dest}")


@app.command()
def benchmark(
    path: Path = typer.Argument(
        Path("benchmarks"),
        help="Benchmark directory or a single suite.yaml",
    ),
    format: str = typer.Option("markdown", "--format"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    scale: str | None = typer.Option(None, "--scale", help="Comma-separated sizes, e.g. 100,500,1000"),
) -> None:
    """Score constructed suites against ground-truth metadata."""
    try:
        if path.is_file():
            payload = {"benchmarks": [run_benchmark(path, path.parent / "benchmark_metadata.yaml")]}
        else:
            payload = run_all_benchmarks(path)
        if scale:
            from evaltrim.benchmark import run_scale_benchmark

            sizes = [int(x) for x in scale.split(",") if x.strip()]
            payload["scale"] = run_scale_benchmark(sizes)
    except EvalTrimError as exc:
        _fail(exc)
    if format == "json":
        import json

        text = json.dumps(payload, indent=2)
    else:
        text = _benchmark_markdown(payload)
    _write(text, output)


def _print_table(result) -> None:
    table = Table(title="EvalTrim recommendations")
    table.add_column("Test")
    table.add_column("State")
    table.add_column("Value")
    table.add_column("Unique")
    for ev in result.evidence:
        table.add_row(
            ev.test_id,
            ev.recommendation.state.value,
            f"{ev.value_score:.1f}",
            ", ".join(ev.unique_atoms[:3]) or "—",
        )
    console.print(table)
    console.print(
        f"KEEP {result.summary.keep} · MERGE {result.summary.merge} · "
        f"RETIRE {result.summary.retire} · REVIEW {result.summary.review}"
    )


def _benchmark_markdown(payload: dict) -> str:
    lines = ["# EvalTrim benchmark", "", "Targets are goals, not claims.", ""]
    for row in payload.get("benchmarks", []):
        lines.append(f"## {row.get('suite')}")
        lines.append(f"- tests: {row.get('tests')}")
        lines.append(f"- runtime_seconds: {row.get('runtime_seconds')}")
        lines.append(f"- deterministic: {row.get('deterministic')}")
        lines.append(f"- redundancy_precision: {row.get('redundancy_precision')}")
        lines.append(f"- redundancy_recall: {row.get('redundancy_recall')}")
        lines.append(f"- retirement_safety_rate: {row.get('retirement_safety_rate')}")
        lines.append(f"- critical_coverage: {row.get('critical_coverage')}")
        lines.append(f"- suite_reduction: {row.get('suite_reduction')}")
        lines.append(f"- KEEP/MERGE/RETIRE/REVIEW: {row['keep']}/{row['merge']}/{row['retire']}/{row['review']}")
        if row.get("unsafe_retirements"):
            lines.append(f"- unsafe_retirements: {row['unsafe_retirements']}")
        lines.append("")
    if payload.get("scale"):
        lines.append("## Scale (generated, no quality labels)")
        for row in payload["scale"]:
            lines.append(
                f"- n={row['tests']} runtime={row['runtime_seconds']}s "
                f"peak_mib={row['peak_mib']} pairs={row['candidate_pairs']}"
            )
        lines.append("")
    return "\n".join(lines)


@app.command()
def check(
    suite: Path = typer.Argument(..., help="Suite to analyze against policy."),
    config: Path | None = typer.Option(None, "--config", help="evaltrim.yaml path."),
) -> None:
    """Apply policy-as-code (exit 3 on violation). Exit codes: 0 pass, 2 invalid, 3 policy, 4 internal."""
    try:
        loaded = load_suite(suite)
        overlay = load_policy_file(config or discover_policy(suite.parent))
        if overlay:
            loaded.config = merge_config(loaded.config, overlay)
        result = analyze_suite(loaded)
        problems = evaluate_policies(result, loaded.config.policies)
    except EvalTrimError as exc:
        _fail(exc)
    if problems:
        _fail(StrictModeError("Policy check failed:\n- " + "\n- ".join(problems)))
    console.print("[green]Policy check passed[/green]")


@app.command()
def run(
    suite: Path = typer.Argument(...),
    agent: str = typer.Option("echo-expected", "--agent", help="echo-expected|echo-input|command|mock"),
    command: str | None = typer.Option(None, "--command", help="Local command for --agent command"),
    repeats: int = typer.Option(1, "--repeats", min=1),
    workers: int = typer.Option(1, "--workers", min=1),
    dry_run: bool = typer.Option(False, "--dry-run"),
    smoke: int | None = typer.Option(None, "--smoke", help="Only the first N cases"),
    record: Path | None = typer.Option(None, "--record", help="Write a replay recording JSON"),
    format: str = typer.Option("markdown", "--format"),
) -> None:
    """Run graders against a local agent adapter. Default adapter echoes expected (offline)."""
    try:
        loaded = _load(suite)
        adapter = resolve_adapter(agent, command.split() if command else None)
        batch = run_suite(loaded, adapter=adapter, repeats=repeats, workers=workers, dry_run=dry_run, smoke=smoke)
    except EvalTrimError as exc:
        _fail(exc)
    except ValueError as exc:
        _fail(InternalError(str(exc)))
    if record and not dry_run:
        save_recording(record, batch)
        console.print(f"Wrote recording {record}")
    if format == "json":
        import json

        console.print(
            json.dumps(
                {
                    "adapter": batch.adapter,
                    "summary": batch.summary,
                    "runtime_seconds": batch.runtime_seconds,
                    "dry_run": batch.dry_run,
                    "cases": [
                        {"id": c.record_id, "passed": c.passed, "fingerprint": c.fingerprint} for c in batch.cases
                    ],
                },
                indent=2,
            )
        )
        return
    console.print(f"Adapter: {batch.adapter}  repeats={batch.repeats}  dry_run={batch.dry_run}")
    console.print(str(batch.summary))


@app.command()
def replay(
    recording: Path = typer.Argument(..., help="Recording JSON from evaltrim run --record"),
    suite: Path = typer.Argument(..., help="Suite used to re-grade recorded outputs"),
) -> None:
    """Re-grade a saved recording without calling the agent."""
    try:
        loaded = _load(suite)
        records = [EvaluationRecord.from_test_case(t) for t in loaded.tests]
        batch = replay_recording(recording, records)
    except EvalTrimError as exc:
        _fail(exc)
    console.print(f"Replayed {len(batch.cases)} cases from {recording}")
    passed = sum(1 for c in batch.cases if c.passed)
    console.print(f"Passed: {passed}/{len(batch.cases)}")


snapshot_app = typer.Typer(help="Save and compare local analysis snapshots.")
app.add_typer(snapshot_app, name="snapshot")


@snapshot_app.command("save")
def snapshot_save(
    name: str = typer.Argument(...),
    suite: Path = typer.Argument(...),
) -> None:
    """Analyze a suite and store the result under .evaltrim/snapshots/."""
    try:
        result = analyze_suite(_load(suite))
        path = save_analysis(name, result)
    except EvalTrimError as exc:
        _fail(exc)
    console.print(f"Saved snapshot {path}")


@snapshot_app.command("list")
def snapshot_list() -> None:
    names = list_snapshots()
    if not names:
        console.print(f"No snapshots in {snapshot_dir()}")
        return
    for name in names:
        console.print(name)


@snapshot_app.command("compare")
def snapshot_compare(
    baseline: str = typer.Argument(...),
    current: str = typer.Argument(...),
    format: str = typer.Option("markdown", "--format"),
) -> None:
    """Compare two named snapshots. This is a suite-analysis diff, not a live agent verdict."""
    try:
        diff = compare_analysis(load_analysis(baseline), load_analysis(current))
    except Exception as exc:  # noqa: BLE001
        _fail(InternalError(str(exc)))
    _print_diff(diff, format)


@app.command()
def compare(
    baseline: Path = typer.Argument(..., help="Baseline suite YAML/JSON"),
    current: Path = typer.Argument(..., help="Current suite YAML/JSON"),
    format: str = typer.Option("markdown", "--format"),
) -> None:
    """Analyze two suites and diff coverage/recommendations. Not a live-agent regression claim."""
    try:
        diff = compare_analysis(analyze_suite(_load(baseline)), analyze_suite(_load(current)))
    except EvalTrimError as exc:
        _fail(exc)
    _print_diff(diff, format)


@app.command("import-jsonl")
def import_jsonl_cmd(
    source: Path = typer.Argument(..., help="JSONL file"),
    output: Path = typer.Option(..., "--output", "-o", help="Destination JSON suite"),
) -> None:
    """Import JSONL eval rows into an EvalTrim JSON suite."""
    try:
        suite_obj = import_jsonl(source)
        write_suite(suite_obj, output)
    except EvalTrimError as exc:
        _fail(exc)
    console.print(f"Imported {len(suite_obj.tests)} tests → {output}")


def _print_diff(diff: dict, format: str) -> None:
    if format == "json":
        import json

        console.print(json.dumps(diff, indent=2))
        return
    tests = diff["tests"]
    crit = diff["critical_coverage"]
    atoms = diff["behavior_atoms"]
    console.print("## EvalTrim suite diff")
    console.print(f"Tests: {tests['before']} -> {tests['after']}")
    console.print(f"Critical coverage: {crit['before'] * 100:.1f}% -> {crit['after'] * 100:.1f}%")
    console.print(f"New behaviors: {len(atoms['new'])}")
    console.print(f"Removed behaviors: {len(atoms['removed'])}")
    console.print(f"Potential suite-diff risk: {diff['suite_diff_risk']}")
    console.print(diff["note"])


if __name__ == "__main__":
    app()
