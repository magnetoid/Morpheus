---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/errors/views.py

Symbols in `core/errors/views.py`.

- L31 `_rate_limited(request)` (function) — Return True if this IP has exhausted its quota in the current window.
- L49 `client_error_ingest(request: HttpRequest)` (function) — Receive JS errors from the browser.
- L94 `_origin_allowed(origin: str)` (function)
- L117 `errors_list(request: HttpRequest)` (function) — Grouped list of recent errors — one row per fingerprint.
- L204 `errors_detail(request: HttpRequest, fingerprint: str)` (function) — Drill-in: all occurrences of one fingerprint.
