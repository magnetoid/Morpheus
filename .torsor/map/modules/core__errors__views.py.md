---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/errors/views.py

Symbols in `core/errors/views.py`.

- L30 `_rate_limited(request)` (function) — Return True if this IP has exhausted its quota in the current window.
- L48 `client_error_ingest(request: HttpRequest)` (function) — Receive JS errors from the browser.
- L93 `_origin_allowed(origin: str)` (function)
- L111 `errors_list(request: HttpRequest)` (function) — Grouped list of recent errors — one row per fingerprint.
- L192 `errors_detail(request: HttpRequest, fingerprint: str)` (function) — Drill-in: all occurrences of one fingerprint.
