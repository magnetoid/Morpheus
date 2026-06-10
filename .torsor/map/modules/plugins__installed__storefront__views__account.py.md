---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/storefront/views/account.py

Symbols in `plugins/installed/storefront/views/account.py`.

- L18 `_login_required(request, target)` (function)
- L26 `_account_summary(user)` (function) — Cheap counts + balances for the account home dashboard.
- L81 `account_home(request)` (function)
- L97 `account_profile(request)` (function)
- L117 `account_orders(request)` (function)
- L131 `account_order_detail(request, order_number)` (function)
- L147 `account_addresses(request)` (function)
- L155 `account_address_form(request, address_id=None)` (function)
- L193 `account_address_delete(request, address_id)` (function)
- L206 `account_returns(request)` (function)
- L223 `account_return_status(request, rma_id)` (function) — Per-RMA status page — four-step pill row so the customer can
- L281 `account_order_return(request, order_number)` (function)
- L314 `account_credits(request)` (function) — Combined view: store-credit balance + ledger + active gift cards.
- L360 `account_data_export(request)` (function) — GDPR Art. 15 — right to access.
- L394 `account_delete(request)` (function) — GDPR Art. 17 — right to be forgotten.
- L434 `account_payment_methods(request)` (function) — Saved card vault — list + add (SetupIntent) + delete.
- L491 `order_confirmation(request, order_number)` (function) — Order confirmation — auth'd customer OR ?token=<public_token>.
