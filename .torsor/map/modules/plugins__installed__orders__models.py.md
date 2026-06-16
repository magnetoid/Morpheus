---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/orders/models.py

Symbols in `plugins/installed/orders/models.py`.

- L18 `_gen_public_token()` (function) — Unguessable token for public order-confirmation access.
- L29 `Cart` (class) — Session or customer cart.
- L58 `__str__(self)` (method)
- L63 `subtotal(self)` (method)
- L72 `item_count(self)` (method)
- L76 `CartItem` (class)
- L94 `__str__(self)` (method)
- L98 `total_price(self)` (method)
- L102 `OrderEvent` (class) — Immutable Event Source for Orders. Every state change is recorded here.
- L122 `Order` (class)
- L206 `__str__(self)` (method)
- L209 `save(self, *args, **kwargs)` (method)
- L219 `_generate_order_number(self)` (method)
- L227 `log_event(self, event_type, message='', prev_state='', new_state=None)` (method)
- L240 `confirm(self)` (method)
- L244 `process(self)` (method)
- L252 `fulfill(self)` (method)
- L260 `ship(self, tracking_number: str='')` (method)
- L268 `deliver(self)` (method)
- L272 `cancel(self, reason='')` (method)
- L280 `OrderItem` (class)
- L304 `__str__(self)` (method)
- L308 `Fulfillment` (class) — Tracks shipment of order items.
- L330 `__str__(self)` (method)
- L334 `FulfillmentItem` (class)
- L339 `__str__(self)` (method)
- L343 `Refund` (class) — Order refunds.
- L363 `__str__(self)` (method)
- L372 `StoreCredit` (class) — Per-customer store-credit balance.
- L392 `__str__(self)` (method)
- L396 `StoreCreditTxn` (class) — Immutable ledger of store-credit changes.
- L433 `__str__(self)` (method)
