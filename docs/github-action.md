# GitHub Action

Workflow: `.github/workflows/evaltrim.yml`

Steps:

- analyze (markdown, JSON, HTML)
- `evaltrim health` / `debt` / `maintain` JSON artifacts
- `evaltrim impacted-tests` from `git diff` paths when available
- optional `evaltrim compare` when a baseline suite path is provided
- `evaltrim check` only when `strict=true`
- upload `artifacts/`
- short PR comment (`evaltrim-pr.md`); full detail stays in artifacts

No hosted backend. Tokens never leave GitHub’s action environment except whatever you already configured for `github-script`.
