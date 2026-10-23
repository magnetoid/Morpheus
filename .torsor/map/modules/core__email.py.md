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

# core/email.py

Symbols in `core/email.py`.

- L13 `smtp_configured()` (function) — Whether outbound email has a real transport (StoreSettings or env).
- L28 `MorpheusEmailBackend` (class) — Composite email backend.
- L40 `__init__(self, fail_silently=False, **kwargs)` (method)
- L81 `send_messages(self, email_messages)` (method)
- L93 `__getattr__(self, name)` (method)
