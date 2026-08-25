# Watch and impacted tests

## Watch

`evaltrim watch SUITE --root . --debounce 0.75`

`--once` scans targets and exits (for tests/CI). The loop debounces events and does not start overlapping analyses.

Relevant suffixes: yaml/yml/json/py plus names containing prompt, eval, suite, tool, policy, agent, config.

## Impacted tests

`evaltrim impacted-tests SUITE path [path ...]`

Priorities: DIRECT, ADJACENT, CRITICAL, LOW_PRIORITY.

Signals: `provenance_files`, `tool_dependencies`, requirement ids, domain name in the path, shared `failure_family`. This is **not** a complete program-dependence graph.
