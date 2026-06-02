---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/marketplace/views.py

Symbols in `plugins/installed/marketplace/views.py`.

- L38 `apply(request: HttpRequest)` (function) — Vendor application form. Creates a `submitted` VendorApplication.
- L82 `dashboard(request: HttpRequest)` (function) — Vendor dashboard for the signed-in customer.
- L152 `_resolve_vendor(user)` (function) — Return the catalog.Vendor row owned by `user`, or None.
- L164 `vendor_products(request: HttpRequest)` (function) — List the signed-in vendor's products. Approved vendors only.
- L192 `vendor_product_edit(request: HttpRequest, product_id)` (function) — Edit one of the signed-in vendor's products. The product must
- L269 `vendor_order_detail(request: HttpRequest, vendor_order_id)` (function) — Per-vendor order detail. Update status + tracking from one screen.
- L354 `vendor_payouts(request: HttpRequest)` (function) — Accrued balance + request payout + history.
- L421 `vendor_settings(request: HttpRequest)` (function) — Edit vendor profile + payout account from the storefront.
