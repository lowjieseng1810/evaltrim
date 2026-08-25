# Suite health and evaluation debt

`evaltrim health SUITE` returns a **heuristic** composite plus component scores: coverage, critical coverage, redundancy, diversity, freshness, flakiness, oracle health, conflicts, provenance, maintainability.

`evaltrim debt SUITE` lists stale, redundant, low-value, flaky, quarantined, conflicts, uncovered requirements, missing provenance, and uncertainty.

Flaky tests are classified STABLE / FLAKY / DEGRADED / QUARANTINED and are **never auto-deleted**.
