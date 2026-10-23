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

# plugins/installed/marketplace/dashboard.py

Symbols in `plugins/installed/marketplace/dashboard.py`.

- L25 `_trail(*items)` (function)
- L29 `_default_commission_percent()` (function) — Read the platform's default commission percent from plugin config.
- L44 `_vendor_commission_percent(vendor)` (function) — Effective commission % for a vendor.
- L73 `vendors_list(request)` (function)
- L113 `applications_list(request)` (function) — Approve / reject incoming vendor applications. On approval,
- L185 `_handle_commission_post(request, vendor, ct)` (function) — Process commission set/clear POST. Returns True if redirect needed.
- L219 `_top_skus_from_snapshots(vorders)` (function) — Flatten items_snapshot rows and return the top-10 sku/name by quantity.
- L241 `vendor_detail(request, vendor_id)` (function) — Per-vendor analytics + commission override editor.
- L321 `vendor_edit(request, vendor_id)` (function) — Edit a vendor's name, web address, description, logo and status.
- L355 `vendor_orders(request)` (function)
- L380 `_handle_payouts_bulk_paid(request)` (function)
- L399 `_handle_payout_single_action(request)` (function)
- L421 `_payouts_csv_response(qs)` (function)
- L458 `payouts(request)` (function)
- L498 `payout_accounts(request)` (function) — Manage VendorPayoutAccount rows — how each vendor gets paid.
- L533 `reports(request)` (function) — Vendor performance — GMV per vendor, recent activity, sparkline.
