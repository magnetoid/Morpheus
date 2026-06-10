---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# core/request_id.py

Symbols in `core/request_id.py`.

- L20 `current_request_id()` (function) — Return the request id for the current execution context (or '-').
- L25 `RequestIdMiddleware` (class) — Generate / propagate a request id, store it in the contextvar.
- L35 `__init__(self, get_response)` (method)
- L38 `__call__(self, request)` (method)
- L53 `RequestIdFilter` (class) — Logging filter that attaches `request_id` to every record.
- L56 `filter(self, record: logging.LogRecord)` (method)
