---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/cart_abandonment/services.py

Symbols in `plugins/installed/cart_abandonment/services.py`.

- L19 `unsubscribe_token(email: str)` (function) — A signed, URL-safe token identifying ``email`` for one-click unsubscribe.
- L24 `email_from_token(token: str)` (function) — Recover the address from a token, or None if it's forged/garbled.
- L36 `recovery_unsubscribe_url(email: str)` (function) — The absolute one-click unsubscribe URL for ``email``.
- L43 `unsubscribe_headers(email: str)` (function) — The RFC 8058 one-click header pair for a cart-recovery send to ``email``.
- L52 `is_suppressed(email: str)` (function) — True if ``email`` has unsubscribed from cart-recovery.
- L62 `suppress_from_token(token: str)` (function) — Record the opt-out for a token's address (idempotent). Returns the email,
