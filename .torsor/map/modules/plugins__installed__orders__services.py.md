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

# plugins/installed/orders/services.py

Symbols in `plugins/installed/orders/services.py`.

- L27 `_is_prelaunch_preview(product)` (function) — A noindex product while the store sells no noindex product (pre-launch).
- L44 `CouponNoLongerValid` (class) — Raised at capture time when a coupon's usage limit is reached, so the
- L50 `GiftCardRedeemFailed` (class) — Raised when a gift card fails to redeem at checkout (expired/disabled/
- L58 `StoreCreditRedeemFailed` (class) — Raised when store credit can't be debited at checkout (a balance race).
- L63 `LoyaltyRedeemFailed` (class) — Raised when a loyalty-points redemption fails at checkout (balance
- L84 `paid_order_items_qs()` (function) — OrderItems from orders that represent a completed purchase (see PAID_STATUSES).
- L89 `CartService` (class)
- L91 `get_or_create_cart(cls, session_key: str='', customer=None)` (method)
- L99 `add_item(cls, cart: Cart, product_id: str, quantity: int=1, variant_id: str | None=None, currency: str | None=None)` (method) — Add a line item, picking the buyer-currency override if available.
- L204 `merge_carts(*, source_cart: Cart, target_cart: Cart)` (function) — Move items from ``source_cart`` into ``target_cart`` and delete the source.
- L233 `_is_inventoried(product, variant)` (function) — True when this product/variant tracks physical stock and should
- L258 `_resolve_unit_price(target, currency: str | None, *, fallback, customer=None)` (function) — Return a ``Money`` honoring ``target.localized_prices[currency]``
- L285 `_order_metadata(visitor_id: str, breakdown: dict, consent: dict | None=None)` (function) — Order metadata, including any named charges the breakdown added on top
- L310 `OrderService` (class)
- L312 `calculate_cart_breakdown(cls, *, cart: Cart, address: dict | None=None, billing_address: dict | None=None, shipping_rate_id: str='')` (method)
- L395 `create_from_cart(cls, cart: Cart, email: str, shipping_address: dict, billing_address: dict, *, visitor_id: str='', consent: dict | None=None)` (method)
- L715 `confirm_order(cls, order: Order)` (method)
- L721 `merge_session_cart_on_login(request, user)` (function) — Reconcile the anonymous-session cart with the customer's cart.
