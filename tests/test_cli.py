from pathlib import Path

from typer.testing import CliRunner

from evaltrim.cli import app

runner = CliRunner()
DEMO = Path("examples/demo_suite.yaml")


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.stdout


def test_validate_demo():
    result = runner.invoke(app, ["validate", str(DEMO)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_analyze_demo_markdown():
    result = runner.invoke(app, ["analyze", str(DEMO)])
    assert result.exit_code == 0
    assert "EvalTrim Report" in result.stdout
    assert "KEEP" in result.stdout


def test_analyze_json_and_github(tmp_path: Path):
    out = tmp_path / "r.json"
    result = runner.invoke(app, ["analyze", str(DEMO), "--format", "json", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    gh = runner.invoke(app, ["analyze", str(DEMO), "--format", "github"])
    assert gh.exit_code == 0
    assert gh.stdout.strip().startswith("## EvalTrim")


def test_simulate_remove():
    result = runner.invoke(app, ["simulate-remove", str(DEMO), "privacy-delete"])
    assert result.exit_code == 0
    assert "KEEP" in result.stdout
    result2 = runner.invoke(app, ["simulate-remove", str(DEMO), "refund-002b"])
    assert result2.exit_code == 0
    assert "SAFE_TO_RETIRE" in result2.stdout or "KEEP" in result2.stdout


def test_unknown_test_id():
    result = runner.invoke(app, ["simulate-remove", str(DEMO), "does-not-exist"])
    assert result.exit_code == 2


def test_init_and_validate(tmp_path: Path):
    path = tmp_path / "evals.yaml"
    result = runner.invoke(app, ["init", str(path)])
    assert result.exit_code == 0
    val = runner.invoke(app, ["validate", str(path)])
    assert val.exit_code == 0


def test_maintain_writes_file(tmp_path: Path):
    dest = tmp_path / "evaltrim-maintenance.md"
    result = runner.invoke(app, ["maintain", str(DEMO), "--output", str(dest)])
    assert result.exit_code == 0
    assert dest.exists()
    assert "Maintenance" in dest.read_text(encoding="utf-8")


def test_strict_fails_on_oracle_conflicts():
    result = runner.invoke(app, ["analyze", str(DEMO), "--strict", "--format", "github"])
    assert result.exit_code == 3


def test_missing_suite_exit_code():
    result = runner.invoke(app, ["validate", "nope.yaml"])
    assert result.exit_code == 2


def test_deterministic_analyze():
    import json

    a = runner.invoke(app, ["analyze", str(DEMO), "--format", "json"])
    b = runner.invoke(app, ["analyze", str(DEMO), "--format", "json"])
    assert a.exit_code == b.exit_code == 0
    da, db = json.loads(a.stdout), json.loads(b.stdout)
    da.pop("timings", None)
    db.pop("timings", None)
    assert da["recommendations"] == db["recommendations"]
