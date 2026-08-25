from pathlib import Path

from typer.testing import CliRunner

from evaltrim.benchmark import run_all_benchmarks
from evaltrim.cli import app
from evaltrim.competitive import run_competitive_harness

runner = CliRunner()


def test_run_all_benchmarks_skips_competitive_dir():
    payload = run_all_benchmarks(Path("benchmarks"))
    suites = [row["suite"] for row in payload["benchmarks"]]
    assert all("competitive" not in s for s in suites)
    assert len(payload["benchmarks"]) >= 3


def test_competitive_harness_does_not_claim_superior():
    payload = run_competitive_harness(scale=[100], write_docs=False)
    assert payload["competitive_status"]["status"] == "GAPS REMAIN"
    assert payload["grader_head_to_head"]["evaltrim_accuracy"] == 1.0
    ae = payload["grader_head_to_head"]["agenteval_accuracy"]
    assert ae == 1.0 or ae == "UNMEASURED"
    for row in payload["metrics"]:
        if "UNMEASURED" in str(row["AgentEval"]) or row["AgentEval"] == "UNMEASURED":
            assert row["winner"] in {"UNMEASURED", "NOT DIRECTLY COMPARABLE"}
        if row["AgentEval"] == "UNMEASURED":
            assert row["winner"] != "EvalTrim"


def test_cli_benchmark_competitive_json():
    result = runner.invoke(app, ["benchmark", "competitive", "--format", "json", "--scale", "100"])
    assert result.exit_code == 0, result.stdout
    assert "GAPS REMAIN" in result.stdout
    assert "UNMEASURED" in result.stdout
    assert "evaltrim_version" in result.stdout
