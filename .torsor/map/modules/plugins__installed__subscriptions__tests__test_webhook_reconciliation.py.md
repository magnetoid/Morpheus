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

# plugins/installed/subscriptions/tests/test_webhook_reconciliation.py

Symbols in `plugins/installed/subscriptions/tests/test_webhook_reconciliation.py`.

- L37 `_customer(**kw)` (function)
- L43 `_invoice_event(event_type, sub_id, *, invoice_id='in_1', amount=1000, currency='usd')` (function)
- L60 `_sub_event(event_type, sub_id, *, status='active', cape=None, periods=True)` (function)
- L70 `InvoicePaidTests` (class)
- L71 `setUp(self)` (method)
- L81 `test_advances_period_and_creates_paid_invoice(self)` (method)
- L95 `test_idempotent_on_second_identical_event(self)` (method)
- L102 `test_leaving_past_due_clears_dunning_marker(self)` (method)
- L115 `test_zero_decimal_currency_amount(self)` (method)
- L123 `test_unknown_subscription_is_noop(self)` (method)
- L130 `InvoiceFailedTests` (class)
- L131 `setUp(self)` (method)
- L141 `test_sets_past_due_opens_invoice_and_arms_dunning(self)` (method)
- L154 `test_repeat_failure_keeps_original_anchor(self)` (method)
- L165 `SubscriptionUpdatedDeletedTests` (class)
- L166 `setUp(self)` (method)
- L176 `test_updated_syncs_state_period_and_cancel_flag(self)` (method)
- L186 `test_updated_back_to_active_clears_dunning(self)` (method)
- L197 `test_deleted_marks_cancelled(self)` (method)
- L205 `test_deleted_incomplete_expired_maps_to_expired(self)` (method)
- L213 `test_unknown_event_type_is_ignored(self)` (method)
- L219 `test_missing_data_object_is_fail_soft(self)` (method)
- L226 `_FakeStripeEvent` (class) — Stands in for a ``stripe.Event`` for process_webhook (non-PI path reads
- L230 `__init__(self, event_id, event_type, obj)` (method)
- L236 `to_dict(self)` (method)
- L240 `WebhookDispatchTests` (class) — The payments-side wiring: unowned events fan out to STRIPE_WEBHOOK_EVENT,
- L244 `setUp(self)` (method)
- L250 `_deliver(self, event)` (method)
- L254 `test_unowned_event_dispatched_to_hook_with_full_payload(self)` (method)
- L263 `test_duplicate_event_id_not_redispatched(self)` (method)
- L271 `test_payment_intent_event_not_dispatched_to_hook(self)` (method)
- L282 `_plan(**kw)` (function)
