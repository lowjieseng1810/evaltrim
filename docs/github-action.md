# GitHub Action

Workflow: `.github/workflows/evaltrim.yml`

It checks out the repo, installs EvalTrim, runs `evaltrim analyze`, uploads `artifacts/evaltrim-report.md` (plus JSON and a PR-sized comment), and optionally comments on the pull request.

## Default vs strict

By default the job **does not fail the build** if the suite looks redundant. Redundancy is a maintenance signal, not a compile error.

Enable strict mode when you want CI to fail on:

- malformed suites (always a hard error from the CLI)
- uncovered declared critical behaviors (`--strict`)
- oracle conflicts (`--strict`)

```yaml
# workflow_dispatch input
strict: "true"
```

or locally:

```bash
evaltrim analyze evals.yaml --strict
```

## PR comment

`evaltrim analyze --format github` prints a short summary suitable for `issues.createComment`. Point reviewers at the uploaded artifact for the full report.
