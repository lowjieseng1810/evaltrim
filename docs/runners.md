# Runners

`evaltrim run` grades a suite against a **local adapter**.

```bash
evaltrim run examples/demo_suite.yaml --agent echo-expected
evaltrim run examples/demo_suite.yaml --dry-run
evaltrim run examples/demo_suite.yaml --smoke 3 --repeats 2
evaltrim run examples/demo_suite.yaml --agent command --command "python my_agent.py" --record rec.json
evaltrim replay rec.json examples/demo_suite.yaml
```

Adapters:

- `echo-expected` / `mock` — returns the expected string (offline tests)
- `echo-input` — echoes the prompt
- `command` — subprocess; JSON `{id,input,expected}` on stdin; JSON `{output}` or plain text on stdout

There is no hosted runner. Cancellation is process-level (Ctrl-C). Parallelism is `--workers N` (threads).
