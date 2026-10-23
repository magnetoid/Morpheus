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

# plugins/installed/subscriptions/tests/test_membership.py

Symbols in `plugins/installed/subscriptions/tests/test_membership.py`.

- L18 `_plan(discount=20, **kw)` (function)
- L29 `_paid_sub(customer, plan, state='active')` (function) — A subscription with EVIDENCE OF PAYMENT.
- L43 `_breakdown(subtotal='100.00')` (function)
- L57 `MemberDiscountHelperTests` (class)
- L58 `setUp(self)` (method)
- L63 `test_zero_for_non_subscriber(self)` (method)
- L66 `test_best_active_discount(self)` (method)
- L71 `test_cancelled_subscription_ignored(self)` (method)
- L76 `CartDiscountHookTests` (class)
- L77 `setUp(self)` (method)
- L82 `test_applies_member_discount(self)` (method)
- L89 `test_no_discount_for_non_member(self)` (method)
- L94 `test_stacks_on_existing_discount(self)` (method)
- L104 `MembershipPageTests` (class)
- L105 `test_page_lists_active_plans(self)` (method)
- L112 `test_subscribe_requires_login(self)` (method)
- L117 `test_logged_in_subscribe_creates_free_membership(self)` (method)
- L126 `test_logged_in_subscribe_refuses_a_paid_plan(self)` (method)
- L137 `PlanManagementTests` (class)
- L138 `setUp(self)` (method)
- L146 `test_create_plan_with_discount(self)` (method)
- L161 `test_update_plan_discount_clamped(self)` (method)
