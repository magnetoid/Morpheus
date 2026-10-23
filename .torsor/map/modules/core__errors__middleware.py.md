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

# core/errors/middleware.py

Symbols in `core/errors/middleware.py`.

- L38 `ErrorCaptureMiddleware` (class) — Record every unhandled exception, then let Django handle it normally.
- L41 `__init__(self, get_response)` (method)
- L44 `__call__(self, request)` (method)
- L59 `process_exception(self, request, exception)` (method)
- L72 `_detailed(self, request, response, started: float)` (method)
