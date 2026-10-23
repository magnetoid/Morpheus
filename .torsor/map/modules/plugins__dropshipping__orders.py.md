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

# plugins/dropshipping/orders.py

Symbols in `plugins/dropshipping/orders.py`.

- L16 `shippable(item)` (function) — Does this order line need a parcel? Digital and virtual lines never go to a supplier.
- L27 `eligible_orders(exclude_relation: str)` (function) — Paid, confirmed/processing orders with a shippable line and no supplier
- L44 `tracking_url(template: str, tracking: str)` (function)
- L51 `ship_with_tracking(order, tracking: str, *, carrier: str='', url: str='')` (function) — Ship ``order`` with ``tracking`` the platform way and return the Fulfillment.
