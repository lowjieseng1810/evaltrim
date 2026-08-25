#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m pip install -e '.[dev]' >/dev/null
echo "== validate =="
evaltrim validate examples/demo_suite.yaml
echo "== analyze =="
evaltrim analyze examples/demo_suite.yaml
echo "== simulate unique critical =="
evaltrim simulate-remove examples/demo_suite.yaml privacy-delete
echo "== simulate redundant duplicate =="
evaltrim simulate-remove examples/demo_suite.yaml refund-002b
echo "== maintain =="
evaltrim maintain examples/demo_suite.yaml --format both
echo "== benchmark =="
evaltrim benchmark benchmarks
echo "Demo complete."
