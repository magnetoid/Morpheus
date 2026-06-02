---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/consent/services.py

Symbols in `plugins/installed/consent/services.py`.

- L36 `read_consent_from_cookie(request: HttpRequest)` (function) — Return the visitor's decision, defaulting to necessary-only.
- L59 `has_decided(request: HttpRequest)` (function) — Has the visitor seen + answered the banner?
- L64 `_hash_ip(request: HttpRequest)` (function)
- L72 `write_consent(request: HttpRequest, response: HttpResponse, *, analytics: bool, marketing: bool, functional: bool, customer: Any=None)` (function) — Persist a decision on the response + in ConsentLog.
