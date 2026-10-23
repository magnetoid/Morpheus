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

# plugins/installed/payments/services/stripe.py

Symbols in `plugins/installed/payments/services/stripe.py`.

- L24 `_ensure_api_key()` (function)
- L28 `get_or_create_stripe_customer(customer)` (function) — Return the Stripe Customer id for this user, creating one if needed.
- L51 `create_setup_intent(customer)` (function) — Mint a SetupIntent for collecting a card without an immediate charge.
- L67 `list_payment_methods(customer)` (function) — Return the customer's saved cards from Stripe (empty list if none).
- L80 `detach_payment_method(payment_method_id: str, customer)` (function) — Detach a card from this customer's vault after verifying ownership.
- L98 `_maybe_attach_to_saved_cards(order, payment_intent_id: str)` (function) — After a PaymentIntent confirms, attach the card to the customer's
- L134 `PaymentService` (class) — Law 5: Business Logic Lives in Services
- L141 `get_stripe_api_key(cls)` (method)
- L148 `get_stripe_public_key(cls)` (method) — The publishable key the Payment Element needs (Settings → Payments, else env).
- L155 `create_payment_intent(cls, order)` (method) — Creates a Stripe PaymentIntent for a given Order.
- L203 `redeem_delegated_token(cls, order, token)` (method) — Charge an ACP Shared Payment Token off-session for `order`.
- L339 `verify_webhook(cls, payload, sig_header)` (method) — Construct + signature-verify a Stripe webhook event.
- L360 `process_webhook(cls, payload, sig_header)` (method) — Processes a Stripe webhook to update transaction statuses.
- L440 `_mark_transaction_success(cls, intent_id)` (method) — Idempotent — the `select_for_update` + status check guarantees
- L491 `_mark_transaction_failed(cls, intent_id, error_msg)` (method) — Atomic + select_for_update to mirror _mark_transaction_success.
- L518 `_dispatch_stripe_event_hook(cls, event_type, payload)` (method) — Offer a non-payment-intent Stripe event to the core hook bus.
