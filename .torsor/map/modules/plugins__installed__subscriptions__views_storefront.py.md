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

# plugins/installed/subscriptions/views_storefront.py

Symbols in `plugins/installed/subscriptions/views_storefront.py`.

- L34 `_is_paid(plan)` (function)
- L38 `_current_membership(user)` (function)
- L50 `_stripe_signup_available()` (function) — A paid plan can only be sold online when Stripe is configured on both
- L61 `membership_view(request)` (function)
- L87 `subscribe_view(request)` (function) — Start a membership on a FREE plan.
- L130 `_welcome(plan)` (function)
- L138 `_paid_stripe_plan_or_redirect(request, plan_id)` (function) — Shared preconditions of the two card-collection views.
- L157 `subscribe_start_view(request, plan_id)` (function) — Card collection for a paid Stripe plan: a SetupIntent + Payment Element.
- L192 `subscribe_confirm_view(request, plan_id)` (function) — Stripe's return leg: verify the SetupIntent, create + start the subscription.
