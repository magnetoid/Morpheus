---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/self_improvement/collectors/error_log.py

Symbols in `core/self_improvement/collectors/error_log.py`.

- L36 `ErrorLogCollector` (class) — Hourly poller. Looks back to the last completed run + small slop;
- L42 `run(self)` (method)
- L58 `_signal_from(self, ev)` (method)
- L80 `_first_meaningful_frame(trace: str)` (method) — Pick the topmost `File ".../app/..."` line — skips
- L97 `_exception_class(message: str)` (method) — `KeyError: 'seo_meta'` -> `KeyError`. Falls back to '?'.
- L106 `_severity_for(ev)` (method)
- L115 `_last_successful_run(self)` (method) — Return the started_at of the most recent successful ingest
- L128 `_error_event_model()` (method) — Resolve observability.ErrorEvent lazily — model might not
