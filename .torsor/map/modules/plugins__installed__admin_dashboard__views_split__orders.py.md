---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/admin_dashboard/views_split/orders.py

Symbols in `plugins/installed/admin_dashboard/views_split/orders.py`.

- L42 `orders_list(request: HttpRequest)` (function)
- L103 `order_detail(request: HttpRequest, order_number: str)` (function)
- L171 `order_new(request: HttpRequest)` (function) — Create a draft order from the dashboard.
- L201 `order_action(request: HttpRequest, order_number: str)` (function) — POST-only side-effects on an existing order (cancel, mark paid, …).
- L260 `order_fulfill(request: HttpRequest, order_number: str)` (function) — Create a Fulfillment record for an order; optionally also flip the
- L287 `order_refund(request: HttpRequest, order_number: str)` (function)
- L309 `orders_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the orders list page.
