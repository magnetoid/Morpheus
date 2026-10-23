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

# core/auth/sign_ins.py

Symbols in `core/auth/sign_ins.py`.

- L45 `describe_device(user_agent: str)` (function) — 'Chrome on Mac' from a user-agent string, or 'Unknown device'.
- L55 `_client_ip(request)` (function) — The visitor's address, by the rule ``core/ratelimit.py:_client_id``
- L72 `record_sign_in(sender, request, user, **kwargs)` (function) — ``user_logged_in`` receiver: one audit entry per successful sign-in.
- L90 `recent_sign_ins(user, limit: int=10)` (function) — The person's newest sign-ins, newest first: ``{'at', 'ip', 'device'}``.
- L107 `prune_sign_ins(keep_days: int=KEEP_DAYS)` (function) — Delete sign-in entries older than ``keep_days``; returns how many.
