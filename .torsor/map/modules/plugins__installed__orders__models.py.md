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
- L210 `__str__(self)` (method)
- L214 `extra_lines(self)` (method) — Named charges on top of the priced lines (e.g. a tree-planting offset),
- L230 `save(self, *args, **kwargs)` (method)
- L240 `_generate_order_number(self)` (method)
- L248 `log_event(self, event_type, message='', prev_state='', new_state=None)` (method)
- L261 `confirm(self)` (method)
- L265 `process(self)` (method)
- L273 `fulfill(self)` (method)
- L281 `ship(self, tracking_number: str='')` (method)
- L289 `deliver(self)` (method)
- L293 `mark_refunded(self, reason='')` (method) — The whole order is refunded (RefundService.record_external).
- L299 `cancel(self, reason='')` (method)
- L307 `OrderItem` (class)
- L331 `__str__(self)` (method)
- L335 `Fulfillment` (class) — Tracks shipment of order items.
- L357 `__str__(self)` (method)
- L361 `FulfillmentItem` (class)
- L366 `__str__(self)` (method)
- L370 `Refund` (class) — Order refunds.
- L390 `__str__(self)` (method)
- L399 `StoreCredit` (class) — Per-customer store-credit balance.
- L419 `__str__(self)` (method)
- L423 `StoreCreditTxn` (class) — Immutable ledger of store-credit changes.
- L460 `__str__(self)` (method)
