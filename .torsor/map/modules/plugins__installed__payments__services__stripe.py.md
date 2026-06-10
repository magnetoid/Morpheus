---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:02'
updated: '2026-06-09T21:57:02'
---

# plugins/installed/payments/services/stripe.py

Symbols in `plugins/installed/payments/services/stripe.py`.

- L22 `_ensure_api_key()` (function)
- L26 `get_or_create_stripe_customer(customer)` (function) — Return the Stripe Customer id for this user, creating one if needed.
- L49 `create_setup_intent(customer)` (function) — Mint a SetupIntent for collecting a card without an immediate charge.
- L65 `list_payment_methods(customer)` (function) — Return the customer's saved cards from Stripe (empty list if none).
- L78 `detach_payment_method(payment_method_id: str, customer)` (function) — Detach a card from this customer's vault after verifying ownership.
- L96 `_maybe_attach_to_saved_cards(order, payment_intent_id: str)` (function) — After a PaymentIntent confirms, attach the card to the customer's
- L132 `PaymentService` (class) — Law 5: Business Logic Lives in Services
- L139 `get_stripe_api_key(cls)` (method)
- L146 `create_payment_intent(cls, order)` (method) — Creates a Stripe PaymentIntent for a given Order.
- L185 `process_webhook(cls, payload, sig_header)` (method) — Processes a Stripe webhook to update transaction statuses.
- L245 `_mark_transaction_success(cls, intent_id)` (method) — Idempotent — the `select_for_update` + status check guarantees
- L288 `_mark_transaction_failed(cls, intent_id, error_msg)` (method) — Atomic + select_for_update to mirror _mark_transaction_success.
