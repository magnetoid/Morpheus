---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
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
- L227 `log_event(self, event_type, message='', prev_state='')` (method)
- L237 `confirm(self)` (method)
- L241 `process(self)` (method)
- L249 `fulfill(self)` (method)
- L257 `ship(self, tracking_number: str='')` (method)
- L263 `deliver(self)` (method)
- L267 `cancel(self, reason='')` (method)
- L275 `OrderItem` (class)
- L299 `__str__(self)` (method)
- L303 `Fulfillment` (class) — Tracks shipment of order items.
- L325 `__str__(self)` (method)
- L329 `FulfillmentItem` (class)
- L334 `__str__(self)` (method)
- L338 `Refund` (class) — Order refunds.
- L358 `__str__(self)` (method)
- L367 `StoreCredit` (class) — Per-customer store-credit balance.
- L387 `__str__(self)` (method)
- L391 `StoreCreditTxn` (class) — Immutable ledger of store-credit changes.
- L428 `__str__(self)` (method)
