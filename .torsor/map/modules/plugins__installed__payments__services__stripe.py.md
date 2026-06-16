---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/installed/payments/services/stripe.py

Symbols in `plugins/installed/payments/services/stripe.py`.

- L23 `_ensure_api_key()` (function)
- L27 `get_or_create_stripe_customer(customer)` (function) — Return the Stripe Customer id for this user, creating one if needed.
- L50 `create_setup_intent(customer)` (function) — Mint a SetupIntent for collecting a card without an immediate charge.
- L66 `list_payment_methods(customer)` (function) — Return the customer's saved cards from Stripe (empty list if none).
- L79 `detach_payment_method(payment_method_id: str, customer)` (function) — Detach a card from this customer's vault after verifying ownership.
- L97 `_maybe_attach_to_saved_cards(order, payment_intent_id: str)` (function) — After a PaymentIntent confirms, attach the card to the customer's
- L133 `PaymentService` (class) — Law 5: Business Logic Lives in Services
- L140 `get_stripe_api_key(cls)` (method)
- L147 `create_payment_intent(cls, order)` (method) — Creates a Stripe PaymentIntent for a given Order.
- L186 `process_webhook(cls, payload, sig_header)` (method) — Processes a Stripe webhook to update transaction statuses.
- L252 `_mark_transaction_success(cls, intent_id)` (method) — Idempotent — the `select_for_update` + status check guarantees
- L299 `_mark_transaction_failed(cls, intent_id, error_msg)` (method) — Atomic + select_for_update to mirror _mark_transaction_success.
