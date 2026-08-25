"""Markdown, JSON, and GitHub PR comment rendering."""

from __future__ import annotations

from evaltrim.intelligence.evidence import render_evidence
from evaltrim.models import (
    AnalysisResult,
    MaintenanceReport,
    Recommendation,
    RecommendationState,
    RemovalSimulation,
    Verdict,
)


def decision_card(rec: Recommendation, *, verbose: bool = False) -> list[str]:
    evd = rec.evidence
    why = rec.reasons[0] if rec.reasons else rec.state.value
    overlap = evd.behavior_overlap if evd else None
    uniq = evd.unique_witnesses_lost if evd else 0
    crit = evd.critical_coverage_lost if evd else 0
    hist = evd.historical_failure_contribution if evd else 0
    drop = evd.counterfactual_coverage_loss if evd else 0
    if rec.state == RecommendationState.KEEP and uniq:
        risk = "HIGH"
        action = "KEEP"
    elif rec.state == RecommendationState.RETIRE:
        risk = "LOW"
        action = "REVIEW / RETIRE"
    elif rec.state == RecommendationState.MERGE:
        risk = "MEDIUM"
        action = "REVIEW / MERGE"
    else:
        risk = "MEDIUM"
        action = rec.state.value
    lines = [
        f"### {rec.state.value} `{rec.test_id}`",
        f"Why: {why}",
        (
            f"Evidence: behavior overlap {overlap} unique witnesses lost {uniq} "
            f"critical coverage loss {crit} historical failure contribution {hist} "
            f"counterfactual loss {drop}"
        ),
        f"Risk: {risk}",
        f"Action: {action}",
    ]
    if verbose and evd:
        lines.append(render_evidence(evd, fmt="markdown"))
    return lines


def render_markdown(result: AnalysisResult, *, verbose: bool = False) -> str:
    s = result.summary
    c = result.coverage
    lines = [
        "# EvalTrim Report",
        "",
        "## Summary",
        "",
        f"{s.test_count} tests analyzed",
        f"{s.keep} recommended KEEP",
        f"{s.merge} MERGE",
        f"{s.retire} RETIRE",
        f"{s.review} REVIEW",
        "",
        "Critical behavior coverage:",
        f"{c.critical_coverage * 100:.1f}%",
        "",
        "Behavior coverage:",
        f"{c.behavior_coverage * 100:.1f}%",
        "",
        "Potential CI reduction:",
        f"{s.estimated_ci_reduction * 100:.0f}%",
        "",
        "> Potential CI reduction counts MERGE + RETIRE recommendations. "
        "It is a review queue, not an automatic deletion plan.",
        "",
        "## Top Retirement Candidates",
        "",
    ]
    retire = [r for r in result.recommendations if r.state == RecommendationState.RETIRE]
    if not retire:
        lines.append("None. No test met the stale + redundant + non-unique bar.")
    else:
        for rec in retire[:20]:
            reason = rec.reasons[0] if rec.reasons else ""
            lines.append(f"- `{rec.test_id}` (value {rec.value_score:.1f}) — {reason}")
    lines += ["", "## Unique Witnesses", ""]
    unique = [w for w in result.witnesses if w.unique_atoms]
    if not unique:
        lines.append("No singleton behavior atoms in this suite.")
    else:
        for w in unique[:30]:
            atoms = ", ".join(w.unique_atoms[:8])
            lines.append(f"- `{w.test_id}`: {atoms}")
    lines += ["", "## Critical Behaviors", ""]
    if s.declared_critical_behaviors:
        for name in s.declared_critical_behaviors:
            status = "covered" if name not in c.uncovered_critical else "**uncovered**"
            lines.append(f"- `{name}`: {status}")
    else:
        lines.append("No `critical_behaviors` declared at suite level.")
    if c.uncovered_critical:
        lines.append("")
        lines.append("Uncovered critical behaviors: " + ", ".join(f"`{x}`" for x in c.uncovered_critical))
    lines += ["", "## Coverage Risks", ""]
    risks = [e for e in result.evidence if e.is_critical_witness]
    if not risks:
        lines.append("No singleton critical witnesses detected.")
    else:
        for e in risks[:20]:
            lines.append(
                f"- `{e.test_id}` uniquely protects critical-adjacent behavior "
                f"({', '.join(e.unique_atoms[:6]) or 'critical flag'})."
            )
    if result.conflicts:
        lines += ["", "Oracle conflicts (similar inputs, diverging expected):"]
        for cid in result.conflicts:
            lines.append(f"- `{cid}`")
    if result.requirement_coverage:
        lines += ["", "## Requirement coverage", ""]
        for row in result.requirement_coverage:
            if row.uncovered:
                warn = "  WARNING: uncovered critical requirement" if row.critical else "  WARNING: uncovered"
                lines.append(f"`{row.requirement_id}` {row.status} covered by: 0 tests{warn}")
            else:
                lines.append(f"`{row.requirement_id}` {row.status} covered by: {len(row.covered_by)} tests")
    lines += ["", "## Recommendations", ""]
    recs = result.recommendations if verbose else result.recommendations[:12]
    for rec in recs:
        lines.extend(decision_card(rec, verbose=verbose))
        lines.append("")
    if not verbose and len(result.recommendations) > 12:
        lines.append(
            f"Showing 12 of {len(result.recommendations)} recommendations. Pass --verbose for the full proof graph."
        )
        lines.append("")
    lines += [
        "## Redundant Pairs",
        "",
    ]
    if not result.pairs:
        lines.append("No pairs above the redundancy threshold.")
    else:
        for pair in result.pairs[:40]:
            lines.append(
                f"- `{pair.left_id}` ↔ `{pair.right_id}`: **{pair.score:.2f}** "
                f"(semantic {pair.semantic:.2f}, behavior {pair.behavior_overlap:.2f}, "
                f"expected {pair.expected_similarity:.2f}, history {pair.historical_overlap:.2f})"
            )
            lines.append(f"  {pair.rationale}")
    lines += ["", "## Methodology", "", result.methodology, ""]
    return "\n".join(lines).rstrip() + "\n"


def render_github_comment(
    result: AnalysisResult,
    *,
    report_path: str = "evaltrim-report.md",
    extra: dict | None = None,
) -> str:
    s = result.summary
    c = result.coverage
    unique_n = sum(1 for w in result.witnesses if w.unique_atoms)
    redundant_n = len({p.left_id for p in result.pairs} | {p.right_id for p in result.pairs})
    crit = f"{c.critical_coverage * 100:.0f}%"
    lines = [
        "## EvalTrim",
        "",
        f"{s.test_count} tests · KEEP {s.keep} · MERGE {s.merge} · RETIRE {s.retire} · REVIEW {s.review}",
        f"Potentially redundant: {redundant_n} · Unique witnesses: {unique_n}",
        f"Critical coverage: {crit} · Review-queue reduction: {s.estimated_ci_reduction * 100:.0f}%",
        "",
    ]
    if c.uncovered_critical:
        lines.append("Critical coverage gaps: " + ", ".join(c.uncovered_critical))
    else:
        lines.append("No declared critical coverage gaps.")
    if result.conflicts:
        lines.append(f"Oracle conflicts requiring REVIEW: {len(result.conflicts)}")
    if extra:
        if extra.get("impacted"):
            lines.append("Impacted tests: " + ", ".join(extra["impacted"][:12]))
        if extra.get("regression"):
            lines.append("Regression summary: " + str(extra["regression"]))
    lines += [
        "",
        "EvalTrim never deletes tests. Full detail is in the workflow artifacts.",
        f"Report: `{report_path}`",
        "",
    ]
    return "\n".join(lines)


def render_html(result: AnalysisResult) -> str:
    s = result.summary
    c = result.coverage
    rows = "".join(
        f"<tr><td>{e.test_id}</td><td>{e.recommendation.state.value}</td>"
        f"<td>{e.value_score:.1f}</td><td>{', '.join(e.unique_atoms[:4]) or '—'}</td></tr>"
        for e in result.evidence
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>EvalTrim report</title>
<style>
body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color: #111; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }}
.muted {{ color: #555; }}
</style></head><body>
<h1>EvalTrim</h1>
<p class="muted">Heuristic local report. Not a hosted dashboard.</p>
<p>{s.test_count} tests · KEEP {s.keep} · MERGE {s.merge} · RETIRE {s.retire} · REVIEW {s.review}</p>
<p>Critical coverage {c.critical_coverage * 100:.1f}% · Behavior coverage {c.behavior_coverage * 100:.1f}%</p>
<table><thead><tr><th>Test</th><th>Recommendation</th><th>Value</th><th>Unique atoms</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="muted">{result.methodology}</p>
</body></html>
"""


def render_simulation_markdown(sim: RemovalSimulation) -> str:
    b, a = sim.before_coverage, sim.after_coverage
    lines = [
        f"# Removal simulation: `{sim.test_id}`",
        "",
        "## BEFORE",
        f"Tests: {sim.before_tests}",
        f"Behavior coverage: {b.behavior_coverage * 100:.1f}%",
        f"Critical coverage: {b.critical_coverage * 100:.1f}%",
        "",
        f"## AFTER removing `{sim.test_id}`",
        f"Tests: {sim.after_tests}",
        f"Behavior coverage: {b.behavior_coverage * 100:.1f}% -> {a.behavior_coverage * 100:.1f}%",
        f"Critical coverage: {b.critical_coverage * 100:.1f}% -> {a.critical_coverage * 100:.1f}%",
        "",
        f"Verdict: **{sim.verdict.value}**",
        "",
    ]
    if sim.verdict == Verdict.KEEP:
        lines.append("Reason: " + (sim.reasons[0] if sim.reasons else "Coverage loss."))
    for reason in sim.reasons:
        lines.append(f"- {reason}")
    if sim.lost_atoms:
        lines += ["", "Lost atoms:", ""]
        for atom in sim.lost_atoms:
            lines.append(f"- `{atom}`")
    lines.append("")
    return "\n".join(lines)


def render_maintenance_markdown(report: MaintenanceReport) -> str:
    s = report.summary
    lines = [
        "# EvalTrim Maintenance Report",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        "",
        "## Snapshot",
        "",
        f"- Tests: {s.test_count}",
        f"- KEEP / MERGE / RETIRE / REVIEW: {s.keep} / {s.merge} / {s.retire} / {s.review}",
        f"- Critical coverage: {report.critical_coverage * 100:.1f}%",
        f"- Estimated suite reduction (review queue): {report.estimated_suite_reduction * 100:.0f}%",
        "",
        "## Candidate merges",
        "",
    ]
    if not report.candidate_merges:
        lines.append("None.")
    else:
        for pair in report.candidate_merges[:40]:
            lines.append(f"- `{pair.left_id}` + `{pair.right_id}` ({pair.score:.2f}) — {pair.rationale}")
    lines += ["", "## Candidate retirements", ""]
    if not report.candidate_retirements:
        lines.append("None.")
    else:
        for rec in report.candidate_retirements:
            lines.append(f"- `{rec.test_id}`: {rec.reasons[0] if rec.reasons else rec.state.value}")
    lines += ["", "## Stale cases", ""]
    if not report.stale_cases:
        lines.append("None flagged.")
    else:
        for tid in report.stale_cases:
            lines.append(f"- `{tid}`")
    lines += ["", "## Unique witnesses", ""]
    for w in report.unique_witnesses[:40]:
        lines.append(f"- `{w.test_id}`: {w.summary}")
    lines += ["", "## Actions (do not modify suites automatically)", ""]
    for action in report.actions[:80]:
        lines.append(f"- `{action.get('test_id')}` → **{action.get('action')}**")
    if report.add_candidates:
        lines += ["", "## ADD_CANDIDATE (not active)", ""]
        for cand in report.add_candidates[:20]:
            lines.append(f"- `{cand.get('kind')}`: {cand.get('suggestion')}")
    lines += ["", "## Evidence notes", ""]
    for note in report.notes:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def result_to_json(result: AnalysisResult) -> str:
    return result.model_dump_json(indent=2)


def maintenance_to_json(report: MaintenanceReport) -> str:
    return report.model_dump_json(indent=2)


def simulation_to_json(sim: RemovalSimulation) -> str:
    return sim.model_dump_json(indent=2)
