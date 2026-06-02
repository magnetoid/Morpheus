---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/storefront/views/account.py

Symbols in `plugins/installed/storefront/views/account.py`.

- L18 `_login_required(request, target)` (function)
- L26 `_account_summary(user)` (function) — Cheap counts + balances for the account home dashboard.
- L111 `account_home(request)` (function)
- L127 `account_profile(request)` (function)
- L147 `account_orders(request)` (function)
- L161 `account_order_detail(request, order_number)` (function)
- L177 `account_addresses(request)` (function)
- L185 `account_address_form(request, address_id=None)` (function)
- L223 `account_address_delete(request, address_id)` (function)
- L236 `account_returns(request)` (function)
- L253 `account_return_status(request, rma_id)` (function) — Per-RMA status page — four-step pill row so the customer can
- L311 `account_order_return(request, order_number)` (function)
- L344 `account_credits(request)` (function) — Combined view: store-credit balance + ledger + active gift cards.
- L384 `account_downloads(request)` (function) — Active digital download links — token-protected, time-bound.
- L415 `account_data_export(request)` (function) — GDPR Art. 15 — right to access.
- L449 `account_delete(request)` (function) — GDPR Art. 17 — right to be forgotten.
- L489 `account_payment_methods(request)` (function) — Saved card vault — list + add (SetupIntent) + delete.
- L546 `order_confirmation(request, order_number)` (function) — Order confirmation — auth'd customer OR ?token=<public_token>.
