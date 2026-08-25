#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m pip install -e '.[dev]' >/dev/null
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
echo "== status / health / explain / doctor =="
evaltrim status examples/demo_suite.yaml --format json | head -c 400; echo
evaltrim health examples/demo_suite.yaml
evaltrim explain privacy-delete --suite examples/demo_suite.yaml
evaltrim doctor --format json | head -c 400; echo
echo "Demo complete."
