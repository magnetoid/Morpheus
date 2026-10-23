---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/marketplace/views.py

Symbols in `plugins/installed/marketplace/views.py`.

- L44 `apply(request: HttpRequest)` (function) — Vendor application form. Creates a `submitted` VendorApplication.
- L83 `_resolve_vendor(user)` (function) — Return the active catalog.Vendor owned by `user`, or None.
- L94 `_shell(request, vendor, active: str, title: str, application=None, **extra)` (function)
- L104 `_account(vendor)` (function)
- L113 `dashboard(request: HttpRequest)` (function) — The vendor's overview — or, before there is a shop, where the
- L164 `vendor_orders(request: HttpRequest)` (function) — Every slice of an order that is this vendor's to send, newest first, with
- L237 `vendor_products(request: HttpRequest)` (function) — The signed-in vendor's products with status, price, stock and recent sales.
- L288 `vendor_product_edit(request: HttpRequest, product_id)` (function) — Edit one of the signed-in vendor's products. The product must
- L368 `_safe_next(request, default: str)` (function)
- L375 `_update_vendor_order(request, vendor_order)` (function) — Apply a vendor's status/tracking update; return an error message or ''.
- L404 `_order_lines(vendor_order)` (function) — The slice's items with unit and line totals, from the order snapshot.
- L431 `vendor_order_detail(request: HttpRequest, vendor_order_id)` (function) — Per-vendor order detail. Update status + tracking from one screen.
- L489 `vendor_payouts(request: HttpRequest)` (function) — Balance, progress to the payout minimum, the request button and history.
- L553 `vendor_settings(request: HttpRequest)` (function) — Edit vendor profile + payout account from the storefront.
