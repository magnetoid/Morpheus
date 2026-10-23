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

# api/views.py

Symbols in `api/views.py`.

- L20 `healthz(request: HttpRequest)` (function) — Liveness — process is up and able to respond.
- L27 `csp_report(request: HttpRequest)` (function) — Content-Security-Policy violation receiver.
- L93 `_fire_csp_hook(**kwargs)` (function) — Fire MorpheusEvents.CSP_VIOLATION_REPORTED for subscribers
- L108 `readyz(request: HttpRequest)` (function) — Readiness — DB and cache are reachable.
- L143 `healthz_deep(request: HttpRequest)` (function) — Deep health — DB + cache + plugin registry + agent runtime + outbox lag.
