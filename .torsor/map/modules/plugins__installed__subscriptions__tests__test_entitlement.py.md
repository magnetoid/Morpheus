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

# plugins/installed/subscriptions/tests/test_entitlement.py

Symbols in `plugins/installed/subscriptions/tests/test_entitlement.py`.

- L27 `_usd(n)` (function)
- L31 `MemberEntitlementTests` (class)
- L32 `setUp(self)` (method)
- L43 `_sub(self, plan, **kw)` (method)
- L50 `test_active_without_any_payment_evidence_is_not_entitled(self)` (method)
- L56 `test_trialing_without_payment_evidence_is_not_entitled(self)` (method)
- L62 `test_free_plan_is_entitled(self)` (method)
- L67 `test_provider_subscription_is_entitled(self)` (method)
- L72 `test_paid_invoice_is_entitled(self)` (method)
- L84 `test_unpaid_invoice_is_not_evidence(self)` (method)
- L97 `test_past_due_is_not_entitled(self)` (method)
- L101 `test_cancelled_is_not_entitled(self)` (method)
- L105 `test_best_of_several_entitling_plans_wins(self)` (method)
- L110 `test_anonymous_gets_nothing(self)` (method)
- L114 `SubscribeViewTests` (class) — The signup path must not hand out paid memberships for nothing.
- L117 `setUp(self)` (method)
- L129 `test_paid_plan_signup_creates_nothing(self)` (method)
- L135 `test_free_plan_signup_still_works(self)` (method)
