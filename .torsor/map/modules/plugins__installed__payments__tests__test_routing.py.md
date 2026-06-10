---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:50'
updated: '2026-06-10T20:08:50'
---

# plugins/installed/payments/tests/test_routing.py

Symbols in `plugins/installed/payments/tests/test_routing.py`.

- L37 `_make_order(amount='42')` (function) — A real, saved Order (routing records the slug on it).
- L46 `_gateway_of(order)` (function) — Read the persisted payment_gateway without refresh_from_db().
- L55 `_FakeIntent` (class) — Mirrors the attributes routing/PaymentService read off a Stripe PI.
- L62 `ResolveGatewayTests` (class) — resolve_gateway() — pure validation against the real registry.
- L65 `test_registry_has_expected_gateways(self)` (method)
- L73 `test_default_is_stripe(self)` (method)
- L76 `test_empty_slug_resolves_to_default(self)` (method)
- L80 `test_unknown_slug_falls_back_to_default(self)` (method)
- L83 `test_enabled_slug_resolves_to_that_gateway(self)` (method)
- L87 `test_disabled_slug_falls_back_to_default(self)` (method)
- L92 `test_explicitly_disabled_slug_is_rejected(self)` (method)
- L96 `test_resolved_gateway_is_a_real_abc_instance(self)` (method)
- L100 `CreatePaymentIntentRoutingTests` (class) — create_payment_intent_for() — the routed money path per gateway.
- L103 `test_stripe_path_returns_stripe_intent_shape(self)` (method)
- L130 `test_empty_slug_uses_stripe_default(self)` (method)
- L147 `test_manual_returns_offline_success(self)` (method)
- L155 `test_cod_returns_offline_success_when_enabled(self)` (method)
- L163 `test_test_gateway_returns_success_when_enabled(self)` (method)
- L171 `test_disabled_slug_falls_back_to_stripe_default(self)` (method)
- L189 `test_unknown_slug_falls_back_to_stripe_default(self)` (method)
- L205 `test_gateway_exception_fails_soft_not_500(self)` (method)
- L217 `PickerGatewaysTests` (class) — picker_gateways() — checkout UI list honours enable flags + default.
- L220 `test_lists_enabled_only_with_default_flag(self)` (method)
- L235 `test_disabled_gateway_drops_out_of_picker(self)` (method)
- L241 `test_configured_instructions_surface(self)` (method)
- L249 `CompleteOrderWiringTests` (class) — Proves the completeOrder resolver threads the chosen slug into the
- L257 `_info(self)` (method)
- L262 `test_resolver_passes_selected_slug_to_router(self)` (method)
