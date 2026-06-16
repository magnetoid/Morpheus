---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/storefront/views/account.py

Symbols in `plugins/installed/storefront/views/account.py`.

- L18 `_login_required(request, target)` (function)
- L26 `_account_summary(user)` (function) — Counts + balances for the account home dashboard.
- L46 `account_home(request)` (function)
- L62 `account_profile(request)` (function)
- L82 `account_orders(request)` (function)
- L96 `account_order_detail(request, order_number)` (function)
- L112 `account_addresses(request)` (function)
- L120 `account_address_form(request, address_id=None)` (function)
- L158 `account_address_delete(request, address_id)` (function)
- L171 `account_returns(request)` (function)
- L188 `account_return_status(request, rma_id)` (function) — Per-RMA status page — four-step pill row so the customer can
- L246 `account_order_return(request, order_number)` (function)
- L279 `account_credits(request)` (function) — Combined view: store-credit balance + ledger + active gift cards.
- L325 `account_data_export(request)` (function) — GDPR Art. 15 — right to access.
- L359 `account_delete(request)` (function) — GDPR Art. 17 — right to be forgotten.
- L399 `account_payment_methods(request)` (function) — Saved card vault — list + add (SetupIntent) + delete.
- L456 `order_confirmation(request, order_number)` (function) — Order confirmation — auth'd customer OR ?token=<public_token>.
