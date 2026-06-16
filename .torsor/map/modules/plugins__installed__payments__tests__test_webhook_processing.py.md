---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/payments/tests/test_webhook_processing.py

Symbols in `plugins/installed/payments/tests/test_webhook_processing.py`.

- L25 `FakeEvent` (class) — Stands in for stripe.Event: just the attributes process_webhook reads.
- L28 `__init__(self, event_id, event_type, intent_id, error_msg='')` (method)
- L38 `to_dict(self)` (method)
- L42 `_order_with_tx(intent_id='pi_test_1')` (function)
- L57 `_deliver(event)` (function) — Run process_webhook with construct_event mocked to return `event`.
- L63 `WebhookSignatureTests` (class)
- L64 `test_invalid_signature_rejected_before_any_write(self)` (method)
- L73 `test_invalid_payload_rejected(self)` (method)
- L82 `PaymentSucceededTests` (class)
- L83 `setUp(self)` (method)
- L89 `test_succeeded_advances_tx_and_order(self)` (method)
- L104 `test_retry_with_same_event_id_is_a_noop(self)` (method)
- L113 `test_second_event_for_same_intent_fires_order_paid_once(self)` (method)
- L122 `test_already_processing_order_only_flips_payment_status(self)` (method)
- L133 `test_unknown_intent_is_recorded_but_changes_nothing(self)` (method)
- L144 `test_handler_failure_is_recorded_and_reraised_for_retry(self)` (method)
- L158 `PaymentFailedTests` (class)
- L159 `test_failed_marks_tx_with_error(self)` (method)
- L175 `test_failed_event_cannot_overwrite_a_success(self)` (method)
