# A8 · Payment link (v0.171.0)

Plan of record: `docs/plans/platform-gap-analysis-2026-11.md`, A8. Owner's go-ahead
2026-11-15 ("Yes, start A8").

## What ships

1. **`/pay/<token>/`**, owned by payments (`views_pay.py`, `urls_pay.py`,
   `templates/payments/pay.html`, which extends the active theme's `storefront/base.html`).
   - The order is found by its `public_token` (43 random characters).
   - A GET only shows the order and the ways to pay (`routing.picker_gateways` for the
     order's customer and whether it ships). It never starts a payment, because email
     link scanners open every link.
   - A POST starts the payment through `routing.create_payment_intent_for`, the checkout's
     own path:
     - Stripe: the session keys the payment step reads, then `/checkout/payment/`;
     - PayPal: its approval URL;
     - bank transfer or cash on delivery: the order confirmation, with the token.
   - Only an open order (`pending`, `confirmed`, `processing`) with
     `payment_status` `unpaid` or `released` can be paid. A paid, held or cancelled order
     says so and offers no form.
   - `never_cache`; noindex through seo's private prefixes (`/pay/`); the title comes from
     `seo_title`.
2. **One Stripe row per intent.** `PaymentService.create_payment_intent` reuses the
   `PaymentTransaction` of an intent it already recorded: Stripe's idempotency key hands
   back the same intent for a second attempt, and each attempt used to add a pending row.
3. **The payment deadline (orders).** A new orders setting, `payment_link_hours`
   (default 72, 0 = no deadline). `orders/payment_deadline.py:hold_for_payment(order, reason)`
   writes `metadata['pay_by']` through the `PAYMENT_LINK_DEADLINE` filter.
   `expire_pending_orders` leaves an order alone while its `pay_by` is ahead (or None),
   and cancels it once that has passed.
   - **Bug fixed on the way:** an order converted from a draft has no gateway, so the
     sweep cancelled it after 60 minutes and released its stock. Converting now holds it
     for payment too.
4. **Payment link email (payments).**
   - `pay_link.send(order, kind)` sends `emails/payment_link` or `emails/payment_failed`
     (both `EmailTemplateDef`s), holds the order and logs `PAYMENT_LINK_SENT`.
   - draft_orders: `services.send_payment_link(draft)` converts an open draft or reuses
     its order. It has a POST view `<number>/send-link/` (`orders.write`) and buttons on
     the draft page (send, resend, the link itself), and the "view orders" link now goes
     to the order.
   - Linda gets `draft_orders.send_payment_link` (`orders.write`, `requires_approval`).
   - draft_orders declares `payments` in `requires`.
5. **Failed payment email (payments).**
   - The setting `failed_payment_email_minutes` defaults to 0, which is off, so no store
     changes on deploy.
   - On `PAYMENT_FAILED`, payments schedules `payments.send_failed_payment_email` after
     commit, with that delay. It sends once per order, and only if the order is still
     payable.
   - The delay must be shorter than the auto-cancel window, or the sweep cancels the
     order first. The setting's description says so.
6. **`Order.notes` → `staff_notes`.** `orders.add_note` and the workflows action
   `add_order_note` wrote a field Order does not have, so both always failed.

## Rulings

- The pay page lives in payments, not the storefront shell. Payments owns the payment
  step (PayPal return, express checkout), and a shell must not import an app for a
  surface.
- `/pay/<token>/` is looked up by the token itself. The token is 256 random bits, so a
  timing difference in an index lookup gives an attacker nothing, and the plan's
  "constant-time" compare is needed only where a token is checked against a known order
  (confirmation).
- The deadline lives in orders, because orders owns the sweep and its window. The link
  and the emails live in payments.
- Partial payment (amount due after an edit) waits for A10. The page charges the order
  total, as checkout does.
- The new copy is wrapped in `{% trans %}`. There are no Serbian or Croatian entries yet,
  so on `/sr/` and `/hr/` it shows in English, like other new checkout copy.

## Tests

- `payments/tests/test_pay_link.py`:
  - a GET starts nothing;
  - unknown token → 404;
  - a paid or cancelled order shows no form;
  - bank transfer → confirmation;
  - Stripe → payment step;
  - PayPal → approval URL;
  - `no-store` and `noindex`;
  - one Stripe row per intent.
- `payments/tests/test_failed_payment_email.py`: off by default; sent once; not sent once
  paid.
- `draft_orders/tests/test_payment_link.py`:
  - converts and emails;
  - resends;
  - no email → nothing converted;
  - holds for payment;
  - the boundary trio on the view;
  - the tool needs approval.
- `orders/tests/test_expire_pending.py`: a `pay_by` ahead keeps the order; one passed
  cancels it; `None` keeps it.
- `orders/tests/test_add_note_staff_notes.py` and the workflows action test.
