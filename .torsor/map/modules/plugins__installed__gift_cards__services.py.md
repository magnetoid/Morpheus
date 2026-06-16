---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/gift_cards/services.py

Symbols in `plugins/installed/gift_cards/services.py`.

- L10 `issue(*, amount: Money, email: str='', issued_by=None, note: str='', expires_at=None)` (function)
- L35 `redeem(*, code: str, amount: Money, reference: str='', actor=None)` (function) — Subtract `amount` from the card's balance. Raises if insufficient.
- L65 `lookup(code: str)` (function)
