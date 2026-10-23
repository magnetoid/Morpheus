---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/storefront/tests/test_order_cancel.py

Symbols in `plugins/installed/storefront/tests/test_order_cancel.py`.

- L20 `_status(order)` (function)
- L26 `_make_order(customer, *, status='pending', payment_status='unpaid')` (function)
- L42 `OrderCancelTests` (class)
- L43 `setUp(self)` (method)
- L53 `_url(self, order)` (method)
- L56 `test_anon_is_redirected_to_login(self)` (method)
- L62 `test_owner_can_cancel_pending_order(self)` (method)
- L69 `test_cancel_refused_after_dispatch(self)` (method)
- L76 `test_get_does_not_cancel(self)` (method)
- L82 `test_cannot_cancel_another_users_order(self)` (method)
- L89 `test_paid_order_is_refunded_in_full(self)` (method)
- L100 `test_unpaid_order_does_not_call_refund(self)` (method)
- L107 `test_refund_failure_still_cancels_the_order(self)` (method)
- L115 `test_cancel_button_shown_only_when_cancellable(self)` (method)
