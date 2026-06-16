---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/promotions/services.py

Symbols in `plugins/installed/promotions/services.py`.

- L26 `AppliedPromotion` (class)
- L36 `_cart_subtotal(cart)` (function) — Best-effort subtotal extraction from arbitrary cart-like objects.
- L62 `_cart_currency(cart, default: str='USD')` (function)
- L72 `_cart_product_ids(cart)` (function)
- L87 `_matches(predicates: dict, *, cart, channel, customer, country, coupon)` (function)
- L118 `_apply_action(action: dict, *, subtotal: Decimal, cart: Any=None)` (function) — Compute the discount amount + flags for one rule action.
- L170 `_apply_bogo(action: dict, *, cart: Any)` (function) — Buy ``buy_qty`` get ``free_qty`` free across the eligible product set.
- L214 `_apply_tiered(action: dict, *, subtotal: Decimal, cart: Any)` (function) — Find the highest tier whose `min_qty` the cart satisfies and
- L237 `evaluate(cart, *, channel: Any=None, customer: Any=None, country: str | None=None, coupon: str | None=None)` (function)
- L294 `models_q_active(now)` (function) — Promotions where (starts_at is null or starts_at <= now) AND (ends_at is null or ends_at > now).
- L303 `record_application(applied: AppliedPromotion, *, order_id: str='', customer_id: str='', currency: str='USD')` (function) — Persist a PromotionApplication + bump times_used atomically.
- L350 `models_f_inc(field_name)` (function)
