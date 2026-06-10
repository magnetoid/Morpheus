---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/marketplace/dashboard.py

Symbols in `plugins/installed/marketplace/dashboard.py`.

- L22 `_trail(*items)` (function) — Standard breadcrumb: Dashboard / Marketplace / <leaf>.
- L33 `_default_commission_percent()` (function) — Read the platform's default commission percent from plugin config.
- L48 `_vendor_commission_percent(vendor)` (function) — Effective commission % for a vendor.
- L76 `vendors_list(request)` (function)
- L115 `applications_list(request)` (function) — Approve / reject incoming vendor applications. On approval,
- L187 `_handle_commission_post(request, vendor, ct)` (function) — Process commission set/clear POST. Returns True if redirect needed.
- L221 `_top_skus_from_snapshots(vorders)` (function) — Flatten items_snapshot rows and return the top-10 sku/name by quantity.
- L242 `vendor_detail(request, vendor_id)` (function) — Per-vendor analytics + commission override editor.
- L321 `vendor_orders(request)` (function)
- L346 `_handle_payouts_bulk_paid(request)` (function)
- L365 `_handle_payout_single_action(request)` (function)
- L387 `_payouts_csv_response(qs)` (function)
- L423 `payouts(request)` (function)
- L462 `payout_accounts(request)` (function) — Manage VendorPayoutAccount rows — how each vendor gets paid.
- L496 `reports(request)` (function) — Vendor performance — GMV per vendor, recent activity, sparkline.
