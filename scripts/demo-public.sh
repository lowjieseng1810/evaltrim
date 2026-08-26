#!/usr/bin/env bash
# Public 1.0 demo. Real commands, real suite, no fabricated values.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
if ! python3 -c "import evaltrim" >/dev/null 2>&1; then
  python3 -m pip install -e '.[dev]'
fi

echo "== analyze =="
python3 -m evaltrim.cli analyze examples/demo_suite.yaml

echo "== unique witness =="
python3 -m evaltrim.cli explain privacy-delete --suite examples/demo_suite.yaml

echo "== removal simulation (critical witness) =="
python3 -m evaltrim.cli simulate-remove examples/demo_suite.yaml privacy-delete

echo "== removal simulation (near-duplicate) =="
python3 -m evaltrim.cli simulate-remove examples/demo_suite.yaml refund-002b

echo "== health =="
python3 -m evaltrim.cli health examples/demo_suite.yaml

echo "== regression (identical suites → UNCHANGED coverage) =="
python3 -m evaltrim.cli compare examples/demo_suite.yaml examples/demo_suite.yaml

echo "== maintain =="
python3 -m evaltrim.cli maintain examples/demo_suite.yaml --format markdown | sed -n '1,40p'

echo "Demo complete."
