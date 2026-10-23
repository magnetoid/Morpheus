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

# plugins/installed/newsletter/services.py

Symbols in `plugins/installed/newsletter/services.py`.

- L15 `_confirm_url(token: str)` (function)
- L21 `_unsubscribe_url(token: str)` (function)
- L27 `subscribe(email: str, *, source: str='popup', customer=None)` (function) — Add an email as a PENDING subscriber and send the confirmation email.
- L66 `confirm(token: str)` (function) — Confirm a pending subscriber. Returns the subscriber or None.
- L89 `unsubscribe(token: str)` (function) — Mark a subscriber unsubscribed (terminal). Returns the subscriber or None.
- L105 `_send_confirm(sub)` (function)
- L116 `_send_welcome(sub)` (function)
- L127 `_send(key: str, sub, subject: str, *, extra: dict)` (function)
