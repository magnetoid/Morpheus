---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# core/request_id.py

Symbols in `core/request_id.py`.

- L22 `current_request_id()` (function) — Return the request id for the current execution context (or '-').
- L27 `RequestIdMiddleware` (class) — Generate / propagate a request id, store it in the contextvar.
- L37 `__init__(self, get_response)` (method)
- L40 `__call__(self, request)` (method)
- L55 `RequestIdFilter` (class) — Logging filter that attaches `request_id` to every record.
- L58 `filter(self, record: logging.LogRecord)` (method)
