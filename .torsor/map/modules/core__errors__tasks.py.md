---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# core/errors/tasks.py

Symbols in `core/errors/tasks.py`.

- L17 `prune_errors_task(keep_days: int=30)` (function) — Daily prune wrapper around the management command logic.
- L46 `error_digest_task(hours: int=24)` (function) — Email the operator the day's server errors, grouped (nothing on a clean day).
- L54 `nightly_health_check()` (function) — Run the health checks; failures are logged and emailed. Returns the failure count.
