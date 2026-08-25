# Network

**Default: no network.**

| Operation | Network |
| --- | --- |
| analyze, status, explain, health, debt, portfolio, maintain, gate, simulate-remove, benchmark | no |
| hashing embeddings (`EVALTRIM_EMBEDDINGS=1`) | no (local) |
| `evaltrim run --agent echo-expected` | no |
| `evaltrim run --agent command --command ...` | only if **your** process talks to the network. EvalTrim uses `subprocess.run(list, shell=False)` and does not interpolate suite text into a shell. |
| LLM extractors | only if `llm_enabled` / `EVALTRIM_LLM` and you configured a provider |

GitHub Action uploads are GitHub’s network, not EvalTrim calling third parties from the library default path.
