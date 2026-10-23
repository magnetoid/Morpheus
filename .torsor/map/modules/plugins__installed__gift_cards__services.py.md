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

# plugins/installed/gift_cards/services.py

Symbols in `plugins/installed/gift_cards/services.py`.

- L14 `issue(*, amount: Money, email: str='', issued_by=None, note: str='', expires_at=None)` (function)
- L39 `redeem(*, code: str, amount: Money, reference: str='', actor=None)` (function) — Subtract `amount` from the card's balance. Raises if insufficient.
- L69 `reverse_redemption_for_order(order)` (function) — Re-credit any gift-card balance spent on ``order`` — idempotent.
- L122 `refund_redemption_for_order(order, refund)` (function) — Re-credit the gift-card tender in proportion to a refund — idempotent.
- L212 `lookup(code: str)` (function)
- L218 `sellable_skus()` (function) — The configured set of order-item SKUs that mean "this is a gift-card
- L227 `issue_for_order(order)` (function) — Issue purchased gift cards for a paid order — idempotent, 1 card/unit.
- L271 `_send_delivery(card, order)` (function) — Email the purchased card's code to the buyer (merchant-editable).
