---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/promotions/services.py

Symbols in `plugins/installed/promotions/services.py`.

- L25 `AppliedPromotion` (class)
- L35 `_cart_subtotal(cart)` (function) — Best-effort subtotal extraction from arbitrary cart-like objects.
- L61 `_cart_currency(cart, default: str='USD')` (function)
- L71 `_cart_product_ids(cart)` (function)
- L86 `_matches(predicates: dict, *, cart, channel, customer, country, coupon)` (function)
- L115 `_apply_action(action: dict, *, subtotal: Decimal, cart: Any=None)` (function) — Compute the discount amount + flags for one rule action.
- L164 `_apply_bogo(action: dict, *, cart: Any)` (function) — Buy ``buy_qty`` get ``free_qty`` free across the eligible product set.
- L208 `_apply_tiered(action: dict, *, subtotal: Decimal, cart: Any)` (function) — Find the highest tier whose `min_qty` the cart satisfies and
- L231 `evaluate(cart, *, channel: Any=None, customer: Any=None, country: Optional[str]=None, coupon: Optional[str]=None)` (function)
- L276 `models_q_active(now)` (function) — Promotions where (starts_at is null or starts_at <= now) AND (ends_at is null or ends_at > now).
- L283 `record_application(applied: AppliedPromotion, *, order_id: str='', customer_id: str='', currency: str='USD')` (function) — Persist a PromotionApplication + bump times_used atomically.
- L329 `models_f_inc(field_name)` (function)
