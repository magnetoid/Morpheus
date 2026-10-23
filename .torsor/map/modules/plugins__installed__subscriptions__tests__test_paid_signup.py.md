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

# plugins/installed/subscriptions/tests/test_paid_signup.py

Symbols in `plugins/installed/subscriptions/tests/test_paid_signup.py`.

- L31 `_plan(**kw)` (function)
- L44 `_Base` (class)
- L45 `setUp(self)` (method)
- L55 `MembershipPageTests` (class)
- L56 `test_paid_stripe_plan_offers_the_card_flow_when_stripe_is_configured(self)` (method)
- L63 `test_paid_plan_is_marked_unavailable_without_stripe(self)` (method)
- L70 `test_paid_manual_plan_is_unavailable_even_with_stripe(self)` (method)
- L76 `test_free_plan_keeps_the_immediate_post_form(self)` (method)
- L85 `SubscribeViewRoutingTests` (class)
- L86 `test_free_plan_activates_immediately(self)` (method)
- L92 `test_paid_stripe_plan_redirects_to_card_collection(self)` (method)
- L100 `test_paid_plan_without_stripe_is_refused_and_creates_nothing(self)` (method)
- L109 `SubscribeStartTests` (class)
- L110 `test_mounts_a_payment_element_on_a_setup_intent(self)` (method)
- L131 `test_setup_intent_failure_degrades_to_a_message_not_a_500(self)` (method)
- L144 `test_free_or_manual_plan_is_not_sold_here(self)` (method)
- L152 `test_existing_member_is_sent_back(self)` (method)
- L160 `test_anonymous_is_sent_to_login(self)` (method)
- L168 `SetupIntentVerificationTests` (class) — `payment_method_from_setup_intent` — the id in the URL is untrusted.
- L171 `setUp(self)` (method)
- L181 `_intent(self, **kw)` (method)
- L186 `test_succeeded_intent_of_this_customer_yields_its_card(self)` (method)
- L192 `test_expanded_payment_method_object_is_handled(self)` (method)
- L198 `test_another_customers_intent_is_refused(self)` (method)
- L203 `test_unfinished_intent_is_refused(self)` (method)
- L210 `test_junk_id_never_reaches_stripe(self)` (method)
- L220 `test_customer_without_a_vault_is_refused_before_stripe(self)` (method)
- L228 `test_stripe_error_is_a_refusal_not_a_crash(self)` (method)
- L239 `SubscribeConfirmTests` (class)
- L240 `_confirm(self, plan, **query)` (method)
- L244 `_fake_start(self, sub, pm_id)` (method)
- L252 `test_happy_path_creates_an_entitled_membership(self)` (method)
- L268 `test_start_failure_leaves_no_membership_row(self)` (method)
- L279 `test_unverified_setup_intent_starts_nothing(self)` (method)
- L291 `test_failed_redirect_status_starts_nothing(self)` (method)
- L303 `test_existing_member_cannot_double_subscribe(self)` (method)
