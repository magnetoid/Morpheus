---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/loyalty_points/services_referrals.py

Symbols in `plugins/installed/loyalty_points/services_referrals.py`.

- L18 `referral_code_for(customer)` (function) — Return (and persist) this customer's permanent referral code.
- L40 `record_referral(*, referrer_code: str, referee)` (function) — Called at signup when referee provides a code. No-op if invalid.
- L56 `qualify_on_order(order)` (function) — Called from ORDER_PLACED — if this is the referee's first
- L123 `_find_referrer(code: str)` (function) — Look up a customer by their stored referral code.
