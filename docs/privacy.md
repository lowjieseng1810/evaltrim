# Privacy

EvalTrim is local-first.

- No hosted backend.
- No telemetry in v0.1.
- No automatic upload of suites or reports.
- Analysis reads a file you pass on the command line and writes files you ask for (`--output`, `evaltrim maintain`).
- LLM adapters are optional interfaces. The default path never sends data off-box.
- If you later set an API key (`EVALTRIM_LLM_PROVIDER` / provider-specific env vars), you are opting in to that vendor’s processing. Do not put keys in the repo.

GitHub Actions only run if you add the workflow to a repository you control; artifacts stay in that GitHub account.
