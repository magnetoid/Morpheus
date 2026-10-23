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

# core/errors/alerts.py

Symbols in `core/errors/alerts.py`.

- L23 `alert_recipients()` (function) — Who hears about problems: ``ERROR_ALERT_EMAILS`` (comma-separated), else the
- L52 `send_alert(subject: str, body: str, connection=None)` (function) — Email ``alert_recipients()``, through ``connection`` when given (one with
- L67 `_errors_link()` (function)
- L73 `build_digest(hours: int=24)` (function) — ``(server error count, email body)`` for the last ``hours``.
- L109 `send_digest(hours: int=24)` (function) — Send the digest when there was at least one server error. Returns the count.
