---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:51'
updated: '2026-06-02T18:07:51'
---

# plugins/installed/admin_dashboard/forms/orders.py

Symbols in `plugins/installed/admin_dashboard/forms/orders.py`.

- L12 `RefundForm` (class) — Issue a refund against an existing order.
- L25 `__init__(self, *args, order=None, **kwargs)` (method)
- L29 `clean_amount(self)` (method)
- L43 `save(self)` (method)
- L71 `FulfillmentForm` (class) — Create a `Fulfillment` row covering the entire order's items.
- L95 `__init__(self, *args, order=None, **kwargs)` (method)
- L99 `save(self)` (method)
- L127 `DraftOrderForm` (class) — Bare-minimum draft order: pick a customer (or just an email) + a note.
- L138 `clean(self)` (method)
- L146 `save(self)` (method)
