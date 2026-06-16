---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/forms/orders.py

Symbols in `plugins/installed/admin_dashboard/forms/orders.py`.

- L13 `RefundForm` (class) — Issue a refund against an existing order.
- L29 `__init__(self, *args, order=None, **kwargs)` (method)
- L33 `clean_amount(self)` (method)
- L47 `save(self)` (method)
- L77 `FulfillmentForm` (class) — Create a `Fulfillment` row covering the entire order's items.
- L105 `__init__(self, *args, order=None, **kwargs)` (method)
- L109 `save(self)` (method)
- L141 `DraftOrderForm` (class) — Bare-minimum draft order: pick a customer (or just an email) + a note.
- L152 `clean(self)` (method)
- L160 `save(self)` (method)
