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

# plugins/installed/orders/tests/test_refund_discount.py

Symbols in `plugins/installed/orders/tests/test_refund_discount.py`.

- L23 `_usd(n)` (function)
- L27 `_make_order(*, subtotal, discount_total, total)` (function)
- L36 `_add_item(order, unit_price, qty=1)` (function)
- L47 `_return(order, *lines)` (function) — lines = (order_item, quantity) tuples.
- L55 `RefundDiscountProrationTests` (class)
- L56 `test_full_return_of_discounted_order_equals_order_total(self)` (method)
- L67 `test_non_discounted_order_refunds_full_line_price(self)` (method)
- L77 `test_partial_return_of_discounted_order_prorates_share(self)` (method)
- L89 `test_refund_clamped_to_remaining_after_prior_refund(self)` (method)
