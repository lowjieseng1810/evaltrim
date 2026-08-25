# Competitive environment

Version lock is `benchmarks/competitive/environment.yaml`. Do not compare tools without that file.

## This machine (2026-08-25)

- OS: Linux 6.12.94+ x86_64
- CPU: 4× Intel Xeon
- RAM: 15 GiB
- Python: 3.12.3
- Node: v22.14.0 (npm 10.9.7)
- Egress: unrestricted (Cursor cloud environment; no linked environment snapshot)
- Competitor packages: `pip install --target /tmp/comp-pkgs` (no `python3-venv` on the image)

## Locked competitors

| Tool | Locked | Reproduced |
| --- | --- | --- |
| EvalTrim | 0.9.0 in-repo | yes |
| AgentEval | PyPI `agentevalkit==0.7.0` | yes (in-process graders / compare / flaky) |
| Promptfoo | attempted 0.122.0 and 0.120.0 | no |
| DeepEval | PyPI latest observed 4.2.0, not installed | no |
| Inspect AI | PyPI latest observed 0.3.260, not installed | no |
| EvalView | not installed | no |
| Vercel agent-eval | not installed | NOT DIRECTLY COMPARABLE |
| Langfuse / Phoenix / Braintrust | — | NOT DIRECTLY COMPARABLE |

## Promptfoo failures

- 0.122.0: `engines.node` requires `>=22.22.0`; host is 22.14.0.
- 0.120.0: `Database migration failed: Can't find meta/_journal.json`.

## Network / privacy

EvalTrim default path requires no network and no API keys. AgentEval llm-judge and semantic extras were not executed. Promptfoo was not executed.
