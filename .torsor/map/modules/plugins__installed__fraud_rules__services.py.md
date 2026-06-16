---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/fraud_rules/services.py

Symbols in `plugins/installed/fraud_rules/services.py`.

- L42 `FraudResult` (class)
- L49 `score_order(order)` (function) — Compute the fraud score + flags for a freshly-placed order.
- L110 `_ip_velocity(order)` (function) — How many orders did this IP place in the last 10 minutes?
- L119 `_email_velocity(order)` (function) — How many orders has this email placed in the last 24 hours?
- L134 `_address_mismatch(order)` (function) — Different countries on shipping vs billing addresses.
- L143 `_bin_high_risk(order)` (function) — Card BIN (first 6 digits) is on the merchant's denylist.
- L157 `_refund_fraud_rate(order)` (function) — Customer's refund ratio over the past 90 days.
- L186 `_is_first_order(order)` (function)
- L195 `_is_high_value(order)` (function)
- L209 `_orders_with_ip(ip: str, *, since)` (function) — How many orders carry this IP in metadata since `since`?
- L223 `_order_ip(order)` (function)
- L230 `_order_email(order)` (function)
- L238 `_country(addr)` (function)
- L244 `_bucket_for(score: int)` (function)
- L254 `_config()` (function)
