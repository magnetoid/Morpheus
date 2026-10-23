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

# plugins/installed/payments/tests/test_routing.py

Symbols in `plugins/installed/payments/tests/test_routing.py`.

- L52 `_make_order(amount='42', customer=None)` (function) — A real, saved Order (routing records the slug on it).
- L62 `_staff()` (function)
- L68 `_bank_transfer_set_up()` (function)
- L74 `_gateway_of(order)` (function) — Read the persisted payment_gateway without refresh_from_db().
- L83 `_FakeIntent` (class) — Mirrors the attributes routing/PaymentService read off a Stripe PI.
- L91 `ResolveGatewayTests` (class) — resolve_gateway() — pure validation against the real registry.
- L94 `setUp(self)` (method)
- L97 `test_registry_has_expected_gateways(self)` (method)
- L105 `test_default_is_stripe(self)` (method)
- L108 `test_empty_slug_resolves_to_default(self)` (method)
- L112 `test_unknown_slug_falls_back_to_default(self)` (method)
- L115 `test_enabled_slug_resolves_to_that_gateway(self)` (method)
- L119 `test_disabled_slug_falls_back_to_default(self)` (method)
- L124 `test_explicitly_disabled_slug_is_rejected(self)` (method)
- L128 `test_resolved_gateway_is_a_real_abc_instance(self)` (method)
- L133 `CreatePaymentIntentRoutingTests` (class) — create_payment_intent_for() — the routed money path per gateway.
- L136 `setUp(self)` (method)
- L139 `test_stripe_path_returns_stripe_intent_shape(self)` (method)
- L166 `test_empty_slug_uses_stripe_default(self)` (method)
- L183 `test_manual_returns_offline_success(self)` (method)
- L191 `test_cod_returns_offline_success_when_enabled(self)` (method)
- L199 `test_test_gateway_returns_success_when_enabled(self)` (method)
- L207 `test_disabled_slug_falls_back_to_stripe_default(self)` (method)
- L225 `test_unknown_slug_falls_back_to_stripe_default(self)` (method)
- L241 `test_gateway_exception_fails_soft_not_500(self)` (method)
- L254 `PickerGatewaysTests` (class) — picker_gateways() — checkout UI list honours enable flags + default.
- L257 `setUp(self)` (method)
- L260 `test_lists_enabled_only_with_default_flag(self)` (method)
- L275 `test_disabled_gateway_drops_out_of_picker(self)` (method)
- L281 `test_configured_instructions_surface(self)` (method)
- L287 `UnconfiguredGatewayTests` (class) — What the live stores had: no Stripe keys and no bank details, so the
- L291 `setUp(self)` (method)
- L294 `test_stripe_without_keys_is_not_offered_or_the_default(self)` (method)
- L299 `test_stripe_needs_both_keys(self)` (method)
- L303 `test_bank_transfer_is_offered_only_with_bank_details(self)` (method)
- L308 `test_the_picker_pre_selects_a_method_that_works(self)` (method)
- L312 `test_an_empty_choice_places_the_order_by_the_working_method(self)` (method)
- L318 `test_nothing_set_up_is_a_clear_error(self)` (method)
- L324 `test_stripe_without_a_key_says_so_plainly(self)` (method)
- L331 `test_stripe_error_text_never_reaches_the_shopper(self)` (method)
- L348 `test_the_sandbox_is_offered_to_staff_only(self)` (method)
- L362 `CompleteOrderWiringTests` (class) — Proves the completeOrder resolver threads the chosen slug into the
- L375 `setUp(self)` (method)
- L393 `_info(self)` (method)
- L401 `test_resolver_passes_selected_slug_to_router(self)` (method)
