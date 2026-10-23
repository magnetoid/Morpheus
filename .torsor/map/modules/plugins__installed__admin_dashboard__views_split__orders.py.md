---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/admin_dashboard/views_split/orders.py

Symbols in `plugins/installed/admin_dashboard/views_split/orders.py`.

- L44 `_awaiting_payment_q()` (function) — Shipped or delivered orders paid offline (cash on delivery, bank transfer)
- L57 `orders_list(request: HttpRequest)` (function)
- L141 `order_detail(request: HttpRequest, order_number: str)` (function)
- L219 `order_new(request: HttpRequest)` (function) — Create a draft order from the dashboard.
- L259 `_mark_order_paid(order)` (function) — Mark an order paid out-of-band (COD, bank transfer, manual) and fire
- L287 `order_action(request: HttpRequest, order_number: str)` (function) — POST-only side-effects on an existing order (cancel, mark paid, …).
- L346 `order_fulfill(request: HttpRequest, order_number: str)` (function) — Create a Fulfillment record for an order; optionally also flip the
- L383 `order_refund(request: HttpRequest, order_number: str)` (function)
- L415 `order_notes(request: HttpRequest, order_number: str)` (function) — Save the staff-only notes on an order (never shown to the customer).
- L430 `order_invoice(request: HttpRequest, order_number: str)` (function) — A print-ready invoice for one order (the browser prints or saves it as PDF).
- L460 `_csv_cell(value)` (function) — One CSV cell. A leading = + - @ makes a spreadsheet run the cell as a
- L467 `_order_export_row(order)` (function)
- L496 `_orders_csv(queryset, filename: str='orders')` (function) — Stream ``queryset`` as a CSV download, newest first.
- L524 `orders_export(request: HttpRequest)` (function) — CSV of the orders the list is showing: same status, search and
- L543 `orders_bulk(request: HttpRequest)` (function) — Bulk action endpoint for the orders list page.
