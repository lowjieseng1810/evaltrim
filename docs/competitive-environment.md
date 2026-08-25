# Competitive environment

Version lock is `benchmarks/competitive/environment.yaml`. Do not compare tools without that file.

## This machine (2026-08-25)

- OS: Linux 6.12.94+ x86_64
- CPU: 4× Intel Xeon
- RAM: 15 GiB
- Python: 3.12.3
- Host Node: v22.14.0
- Isolated Node for Promptfoo: v22.22.0 (`/tmp/evaltrim-comp/node`)
- Egress: unrestricted (Cursor cloud environment)
- Competitors: isolated trees under `/tmp/evaltrim-comp` (not the EvalTrim interpreter)

## Locked competitors

| Tool | Locked | Reproduced |
| --- | --- | --- |
| EvalTrim | 1.0.0 in-repo | yes |
| AgentEval | PyPI `agentevalkit==0.7.0` | yes |
| Promptfoo | npm `0.122.0` on Node 22.22.0 | yes (echo provider eval) |
| DeepEval | PyPI `4.2.0` | yes (ExactMatch/PatternMatch; GEval LLM-DEPENDENT) |
| Inspect AI | PyPI `0.3.260` | yes (mockllm + exact) |
| EvalView | PyPI `0.8.1` | yes (`compare_to_golden`) |
| AgentEvalHQ | NuGet `0.28.0-beta` | yes (ResponseAssertions) |
| Vercel agent-eval | not executed | NOT DIRECTLY COMPARABLE |
| Langfuse / Phoenix / Braintrust | — | NOT DIRECTLY COMPARABLE |

## Network / privacy

EvalTrim default path requires no network and no API keys. Promptfoo ran with `--no-share` and the echo provider. DeepEval GEval was not scored. AgentEval llm-judge extras were not executed.
