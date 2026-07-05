# Stripe Subscription Billing Adapter — Design

**Date:** 2026-07-05 · **Status:** approved (Bet 3 of the mid-2026 trends roadmap,
`docs/plans/trends-2026-adoption.md`) · **Owner plugin:** `plugins/installed/subscriptions/`
(consumes `payments` via its service layer; emails via `core.emails`).

## Context

The subscriptions surface is a demo, not a revenue engine: `subscriptions/`
has the full billing data model — `Plan.provider='stripe'` + `provider_price_id`
(models.py:27-46), `Subscription.provider_subscription_id` (:88),
`SubscriptionInvoice.provider_invoice_id` (:119) — and its plugin.py:13 declares
a "Stripe Billing adapter slot ready", but **no adapter module exists, nothing
advances billing periods, no invoice is ever created, and no payment is ever
taken**. `subscribe_view` (views_storefront.py:32) creates a `Subscription` with
no `current_period_end`. Meanwhile `payments/services/stripe.py` already has the
hard parts: a Stripe customer vault (`get_or_create_stripe_customer` :27,
`Customer.stripe_customer_id`), off-session `create_setup_intent` (:50), saved
payment methods, and idempotent webhook processing (`StripeWebhookEvent`).
Replenishment-subscription economics are the strongest-evidence retention lever
of 2026 (<4%/mo churn; annual billing cuts churn 60–80%).

**Goal:** fill the declared adapter slot — real recurring charging via Stripe
Billing, webhook-driven reconciliation, dunning, and pre-renewal emails.
**Zero migrations** (every provider field already exists).

## Non-goals (this slice)

- `subscriptions_plus` (physical replenishment shipments) billing — separate
  concern/model; it gets wired to this adapter in a later slice.
- Subscribe-at-checkout (cart line → subscription) — new flow, later slice.
- Proration, plan-change/upgrades, usage-based billing, customer portal UI
  beyond a payment-update link.
- Manual-provider auto-rebill (manual stays manual; Stripe plans get real
  billing).

## Design

### 1. Adapter module — `subscriptions/billing/stripe_adapter.py`

Thin, fail-soft wrapper over the `stripe` SDK (key via the payments plugin's
config, same accessor as `PaymentService.get_stripe_api_key`):

- `sync_plan(plan) -> str` — ensure a Stripe Product + Price for a
  `Plan(provider='stripe')` (create if `provider_price_id` blank; amount/
  interval from the Plan), store + return `provider_price_id`. Idempotent.
- `start_subscription(subscription, payment_method_id) -> dict` — ensure
  Stripe customer (`get_or_create_stripe_customer`), attach/set default PM,
  `stripe.Subscription.create(customer, items=[{price}], trial from
  plan.trial_days, metadata={subscription_id})`; store
  `provider_subscription_id`, set `state`/`current_period_start/end` from the
  Stripe object.
- `cancel_subscription(subscription, *, at_period_end=True)` and
  `pause/resume` — mirror the agent-tool lifecycle onto the Stripe object
  (pause via `pause_collection`).

### 2. Storefront subscribe flow (Stripe plans)

`subscribe_view` (views_storefront.py): for `plan.provider == 'stripe'` the
POST returns a payment step — reuse the payments plugin's SetupIntent
machinery (`create_setup_intent`) to collect/select a payment method
(Payment Element), then `start_subscription`. Manual plans keep today's
immediate-create behavior. Anonymous users: unchanged (login required for
stripe plans — subscription needs a Customer row).

### 3. Webhook reconciliation (payments plugin)

Extend `PaymentService.process_webhook` (stripe.py:186) with subscription
events, routed to a handler the subscriptions plugin **registers via a
`core.hooks` filter** (`STRIPE_WEBHOOK_EVENT` — payments fires it for event
types it doesn't own; keeps payments from importing subscriptions):

- `invoice.paid` → upsert `SubscriptionInvoice(state='paid', paid_at,
  provider_invoice_id, period_*, amount)`, advance
  `Subscription.current_period_start/end`, `state='active'`.
- `invoice.payment_failed` → invoice `state='open'`, subscription
  `state='past_due'`, enqueue dunning email (see 4). Stripe Smart Retries
  handles the retry ladder — we mirror state, we don't re-charge.
- `customer.subscription.updated/deleted` → sync state/periods
  (`deleted` → `state='cancelled'`/`expired`).
- Also fix the dangling `PaymentService.verify_webhook` reference in
  `gateways/stripe_gateway.py:68` (method doesn't exist — point it at the
  construct-event logic `process_webhook` uses).

### 4. Dunning + pre-renewal emails (`subscriptions/tasks.py`, new)

Mirror the cart_abandonment drip shape (plugin.py:45-60 beat registration,
consent-gated, per-step stamping):

- **Dunning:** on `past_due`, a drip (day 0 / 3 / 7) via
  `core.emails.send_templated_email('subscription_payment_failed', …)` with a
  payment-update link (SetupIntent flow). Stops when state leaves
  `past_due`. Templates contributed via `contribute_email_templates`.
- **Pre-renewal:** daily beat scans `state='active'` subs with
  `current_period_end` in N days (config, default 3) → send
  `subscription_upcoming_renewal` once per period (stamp in a metadata/sent
  marker on the SubscriptionInvoice draft or subscription row) with
  cancel/pause CTAs (links to the existing account lifecycle endpoints).

### 5. Config

`subscriptions/plugin.py` schema gains: `prerenewal_days` (int, default 3),
`dunning_step_days` (list, default [0,3,7]). Stripe keys stay in the
payments plugin (single owner).

## Contract & safety

- subscriptions → payments coupling stays at the service layer
  (`get_or_create_stripe_customer`, `get_stripe_api_key`) with lazy imports +
  fail-soft (payments disabled → Stripe plans behave as today: no charge,
  logged warning). payments → subscriptions goes through the new hook filter
  only. `requires` gains `payments`? No — optional dep, keep fail-soft (a
  merchant can run manual-only subscriptions without payments).
- All Stripe calls in try/except with `{'success': False, 'error'}` returns
  (never raise into a view/webhook); webhook idempotency via the existing
  `StripeWebhookEvent` unique guard.
- Zero migrations. If a "pre-renewal email sent" marker needs a field, use
  `SubscriptionInvoice` draft rows or a metadata JSON key on Subscription —
  check which exists; do NOT add columns this slice.

## Verification

- Unit (stripe SDK mocked at the `stripe.*` boundary, matching payments'
  test style): plan sync idempotency; start_subscription stores provider id
  + periods; webhook `invoice.paid` advances periods + creates paid invoice;
  `invoice.payment_failed` → past_due + dunning enqueued; subscription.deleted
  → cancelled; duplicate webhook event id → no-op; payments-disabled
  fail-soft.
- Beat: pre-renewal task sends once per period (idempotent), respects
  `prerenewal_days`.
- Suites: `DATABASE_URL='sqlite:///:memory:' python manage.py test
  plugins.installed.subscriptions plugins.installed.payments` green; ruff
  clean; `makemigrations --check` shows no changes (zero-migration promise).
