---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/installed/admin_dashboard/forms/orders.py

Symbols in `plugins/installed/admin_dashboard/forms/orders.py`.

- L13 `RefundForm` (class) — Issue a refund against an existing order.
- L29 `__init__(self, *args, order=None, **kwargs)` (method)
- L33 `clean_amount(self)` (method)
- L47 `save(self, *, actor=None)` (method)
- L67 `FulfillmentForm` (class) — Create a `Fulfillment` row covering the entire order's items.
- L95 `__init__(self, *args, order=None, **kwargs)` (method)
- L99 `save(self)` (method)
- L131 `DraftOrderForm` (class) — Bare-minimum draft order: pick a customer (or just an email) + a note.
- L142 `clean(self)` (method)
- L150 `save(self)` (method)
