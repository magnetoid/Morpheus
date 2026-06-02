---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/gift_cards/services.py

Symbols in `plugins/installed/gift_cards/services.py`.

- L11 `issue(*, amount: Money, email: str='', issued_by=None, note: str='', expires_at=None)` (function)
- L28 `redeem(*, code: str, amount: Money, reference: str='', actor=None)` (function) — Subtract `amount` from the card's balance. Raises if insufficient.
- L56 `lookup(code: str)` (function)
