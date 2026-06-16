---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/views_split/customers.py

Symbols in `plugins/installed/admin_dashboard/views_split/customers.py`.

- L41 `customers_list(request: HttpRequest)` (function) — Unified Contacts list — customers, leads, signups in one table.
- L170 `customer_new(request: HttpRequest)` (function)
- L191 `customer_edit(request: HttpRequest, customer_id: str)` (function)
- L256 `customer_delete(request: HttpRequest, customer_id: str)` (function)
- L276 `_get_customer(customer_id: str)` (function)
- L283 `address_new(request: HttpRequest, customer_id: str)` (function)
- L308 `address_edit(request: HttpRequest, customer_id: str, address_id: str)` (function)
- L336 `address_delete(request: HttpRequest, customer_id: str, address_id: str)` (function)
- L351 `customers_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the customers list page.
