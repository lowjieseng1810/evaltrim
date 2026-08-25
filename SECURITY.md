# Security

EvalTrim is local-first.

- Report vulnerabilities privately to the maintainers of your fork. This repository does not operate a hosted service.
- Do not commit API keys. Optional LLM features read environment variables at runtime only.
- Default execution makes **no** network calls.
- YAML/JSON parsing uses `yaml.safe_load` / `json.loads`.
- `evaltrim run --agent command` executes a **user-supplied argv list** with `shell=False`. Suite contents are sent on stdin as JSON, not interpolated into a shell string.
- EvalTrim never executes tests as code and never deletes suite files.
- Cache and SQLite under `.evaltrim/` or `EVALTRIM_CACHE` / `EVALTRIM_DB` may contain prompts. Treat them as sensitive.
