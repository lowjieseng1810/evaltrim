# Cache and local storage

No server. SQLite file:

- `EVALTRIM_DB` if set
- else `./.evaltrim/evaltrim.sqlite`

Reset: `evaltrim store-reset` (deletes the DB file).

Disable analysis cache: `EVALTRIM_NO_CACHE=1`.

Cache keys include `ANALYSIS_ALGO_VERSION`, `SIMULATION_VERSION`, suite content hashes, and config. Same input → hit. Changed tests → miss. Algorithm bump → miss.

Pair-score cache reuses similarity for unchanged test content hashes. Coverage and unique witnesses still recompute on the current suite.

Corrupt cache values are treated as misses. Corrupt SQLite raises a user-facing internal error on read/write of the store; `evaltrim doctor` checks that the file opens.
