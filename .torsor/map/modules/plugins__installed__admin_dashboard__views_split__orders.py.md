---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/views_split/orders.py

Symbols in `plugins/installed/admin_dashboard/views_split/orders.py`.

- L43 `orders_list(request: HttpRequest)` (function)
- L110 `order_detail(request: HttpRequest, order_number: str)` (function)
- L187 `order_new(request: HttpRequest)` (function) — Create a draft order from the dashboard.
- L222 `order_action(request: HttpRequest, order_number: str)` (function) — POST-only side-effects on an existing order (cancel, mark paid, …).
- L282 `order_fulfill(request: HttpRequest, order_number: str)` (function) — Create a Fulfillment record for an order; optionally also flip the
- L318 `order_refund(request: HttpRequest, order_number: str)` (function)
- L345 `orders_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the orders list page.
