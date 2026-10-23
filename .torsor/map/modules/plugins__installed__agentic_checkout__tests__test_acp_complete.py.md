---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/agentic_checkout/tests/test_acp_complete.py

Symbols in `plugins/installed/agentic_checkout/tests/test_acp_complete.py`.

- L37 `_set_acp_config(**config)` (function)
- L46 `_CompleteTestBase` (class) — Shared fixture + helpers for the ``complete`` money-path suites.
- L49 `setUp(self)` (method)
- L76 `_post(self, path, body=None, token=_TOKEN)` (method)
- L85 `_create_session(self, *, buyer=True, fulfillment=True)` (method)
- L105 `_complete(self, sid, body=None)` (method)
- L111 `_error_codes(session: dict)` (method)
- L115 `AcpCompleteTests` (class)
- L118 `test_payments_disabled_preserves_unsupported(self)` (method)
- L130 `test_complete_success_places_paid_order(self)` (method)
- L163 `test_an_agent_order_records_no_marketing_consent(self)` (method)
- L182 `test_complete_success_records_evidence_metafield(self)` (method)
- L202 `test_retry_after_success_returns_same_order_without_new_charge(self)` (method)
- L216 `test_decline_returns_payment_declined_order_unpaid(self)` (method)
- L241 `test_missing_email_and_address_rejected(self)` (method)
- L254 `test_non_stripe_provider_unsupported(self)` (method)
- L263 `test_empty_token_invalid(self)` (method)
- L272 `AcpCompleteHardeningTests` (class) — Adversarial-review fixes: the completion claim (double-charge race),
- L281 `_cart(self, sid)` (method)
- L284 `_set_claim(self, sid, *, minutes_ago: int=0)` (method)
- L293 `test_fresh_claim_returns_conflict_without_charging(self)` (method)
- L305 `test_stale_claim_is_taken_over(self)` (method)
- L320 `test_retry_after_connection_error_replays_same_key_and_completes(self)` (method)
- L351 `test_processing_result_maps_to_retryable_not_declined(self)` (method)
- L372 `test_total_drift_rejected_before_charge_then_requote_succeeds(self)` (method)
- L402 `test_retry_response_rebuilds_line_items_from_order(self)` (method)
- L425 `AcpEligibilityTests` (class)
- L426 `setUp(self)` (method)
- L444 `_exclude(self, product)` (method)
- L451 `_post(self, path, body, token=_TOKEN)` (method)
- L459 `test_excluded_product_rejected_at_session_create(self)` (method)
- L475 `test_feed_flags_excluded_product_ineligible(self)` (method)
