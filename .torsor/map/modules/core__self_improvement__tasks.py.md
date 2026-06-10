---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/self_improvement/tasks.py

Symbols in `core/self_improvement/tasks.py`.

- L28 `ingest_hourly()` (function) — Run the hour-cadenced collectors (error_log; csp is hook-driven).
- L36 `scan_seo_daily()` (function)
- L43 `scan_drift_daily()` (function)
- L52 `scan_code_weekly()` (function)
- L61 `analyze_nightly(window_hours: int=24)` (function) — Plan-and-execute analyzer pipeline run.
- L69 `execute_queue()` (function) — Phase 2: pick up approved + auto-applied recommendations and
- L78 `digest_weekly()` (function) — Generate + email the weekly engineering digest.
- L113 `register_beat_schedule(schedule: dict)` (function) — Called from morph/celery.py after app.conf.beat_schedule is set.
