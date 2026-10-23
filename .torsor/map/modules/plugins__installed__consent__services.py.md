---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/consent/services.py

Symbols in `plugins/installed/consent/services.py`.

- L36 `read_consent_from_cookie(request: HttpRequest)` (function) — Return the visitor's decision, defaulting to necessary-only.
- L59 `is_gpc(request: HttpRequest)` (function) — The browser sent Global Privacy Control (``Sec-GPC: 1``).
- L64 `has_decided(request: HttpRequest)` (function) — Has the visitor seen + answered the banner?
- L76 `_hash_ip(request: HttpRequest)` (function)
- L84 `write_consent(request: HttpRequest, response: HttpResponse, *, analytics: bool, marketing: bool, functional: bool, customer: Any=None)` (function) — Persist a decision on the response + in ConsentLog.
- L130 `decision_answer(value, request=None, **_)` (function) — CONSENT_DECISION: this visitor's choice, for core/consent.py.
- L142 `marketing_customers_answer(value, **_)` (function) — CONSENT_MARKETING_CUSTOMERS: customers whose LATEST decision allows marketing.
