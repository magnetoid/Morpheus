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

# core/security_headers.py

Symbols in `core/security_headers.py`.

- L131 `dashboard_csp(*, frame_src: tuple[str, ...]=())` (function) — The enforced dashboard policy, letting one response frame `frame_src`.
- L143 `SecurityHeadersMiddleware` (class) — Adds headers Django doesn't ship by default.
- L146 `__init__(self, get_response)` (method)
- L149 `__call__(self, request)` (method)
