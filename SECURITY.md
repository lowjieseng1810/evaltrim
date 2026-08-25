# Security

EvalTrim is local-first.

- Report vulnerabilities privately to the maintainers of your fork; this repository does not operate a hosted service.
- Do not commit API keys. Optional LLM/embedding features read environment variables at runtime only.
- Default execution makes no network calls. `evaltrim run --agent command` executes a **user-supplied** local process.
- Cache files (if embedding persist is on) live under `EVALTRIM_CACHE` or `~/.cache/evaltrim`. Treat them as sensitive if suites contain production prompts.
