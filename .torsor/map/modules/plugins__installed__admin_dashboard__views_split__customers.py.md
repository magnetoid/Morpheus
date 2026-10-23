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

# plugins/installed/admin_dashboard/views_split/customers.py

Symbols in `plugins/installed/admin_dashboard/views_split/customers.py`.

- L44 `customers_list(request: HttpRequest)` (function) — Unified Contacts list — customers, leads, signups in one table.
- L189 `customer_new(request: HttpRequest)` (function)
- L214 `customer_edit(request: HttpRequest, customer_id: str)` (function)
- L283 `customer_delete(request: HttpRequest, customer_id: str)` (function)
- L303 `_get_customer(customer_id: str)` (function)
- L310 `address_new(request: HttpRequest, customer_id: str)` (function)
- L337 `address_edit(request: HttpRequest, customer_id: str, address_id: str)` (function)
- L368 `address_delete(request: HttpRequest, customer_id: str, address_id: str)` (function)
- L383 `customers_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the customers list page.
