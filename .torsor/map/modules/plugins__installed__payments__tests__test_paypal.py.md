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

# plugins/installed/payments/tests/test_paypal.py

Symbols in `plugins/installed/payments/tests/test_paypal.py`.

- L25 `_make_order(amount='42')` (function)
- L33 `_resp(json_data, status=200)` (function)
- L68 `PayPalGatewayTests` (class)
- L69 `setUp(self)` (method)
- L73 `_mock_post(self, responses)` (method) — Patch requests.post to return canned responses per URL substring.
- L84 `test_create_intent_maps_amount_and_returns_approval_url(self)` (method)
- L119 `test_create_intent_failure_bubbles_error(self)` (method)
- L136 `PayPalReturnFlowTests` (class)
- L137 `setUp(self)` (method)
- L149 `_return(self, token='PPORDER1')` (method)
- L156 `test_return_captures_marks_paid_and_fires_order_paid_once(self)` (method)
- L180 `test_return_capture_failure_bounces_to_checkout(self)` (method)
- L193 `test_return_with_unknown_token_bounces(self)` (method)
- L199 `PayPalRefundTests` (class)
- L200 `test_refund_looks_up_capture_and_posts_amount(self)` (method)
- L238 `PayPalWebhookTests` (class)
- L239 `setUp(self)` (method)
- L243 `_post(self, body=b'{}')` (method)
- L248 `test_unverified_webhook_rejected(self)` (method)
- L253 `test_capture_completed_marks_paid_idempotently(self)` (method)
- L278 `test_other_event_types_acked_without_side_effects(self)` (method)
- L286 `ApplePayDomainTests` (class)
- L287 `setUp(self)` (method)
- L291 `test_serves_and_caches_stripe_file(self)` (method)
- L303 `test_fetch_failure_is_404(self)` (method)
- L311 `PayPalPickerTests` (class)
- L312 `test_disabled_paypal_not_in_picker(self)` (method)
- L317 `test_enabled_paypal_in_picker(self)` (method)
- L323 `test_enabled_paypal_without_credentials_is_not_offered(self)` (method)
- L330 `test_sync_gateway_row_projects_toggle_and_credentials(self)` (method)
