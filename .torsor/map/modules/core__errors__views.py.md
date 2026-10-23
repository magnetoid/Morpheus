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

# core/errors/views.py

Symbols in `core/errors/views.py`.

- L33 `_rate_limited(request)` (function) — Return True if this IP has exhausted its quota in the current window.
- L51 `client_error_ingest(request: HttpRequest)` (function) — Receive JS errors from the browser.
- L96 `_origin_allowed(origin: str)` (function)
- L119 `errors_list(request: HttpRequest)` (function) — Grouped list of recent errors — one row per fingerprint.
- L226 `errors_detail(request: HttpRequest, fingerprint: str)` (function) — Drill-in: all occurrences of one fingerprint.
- L252 `errors_report(request: HttpRequest)` (function) — The report for Claude Code: Markdown by default, JSON with ?format=json.
- L284 `errors_detailed(request: HttpRequest)` (function) — Turn detailed capture on for a window, or off.
- L308 `errors_resolve(request: HttpRequest, fingerprint: str)` (function) — Mark a group resolved, or open it again.
