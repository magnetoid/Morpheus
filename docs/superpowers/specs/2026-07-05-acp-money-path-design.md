# ACP Money Path (Phase 2) — Design

**Date:** 2026-07-05 · **Status:** approved (Bet 1 of the mid-2026 trends roadmap,
`docs/plans/trends-2026-adoption.md`) · **Owner plugin:** `plugins/installed/agentic_checkout/`

## Context

Morpheus already ships ACP Phase 1: Bearer+scope-authed checkout-session
endpoints (`create/get/update/cancel` — the session id IS a `Cart` id), a
conformant serializer (`totals[]` from `OrderService.calculate_cart_breakdown`),
`/.well-known/acp.json` + UCP manifest, and an agent product feed. The single
missing piece is the money: `complete_checkout_session`
([views.py:434](../../plugins/installed/agentic_checkout/views.py)) returns a
`MessageError code='unsupported'` under HTTP 422. Meanwhile the market settled
on ACP as the interoperable substrate (ChatGPT ecosystem, Microsoft Copilot
Checkout, PayPal), with the merchant staying merchant-of-record — and Shopify
turned agent checkout on by default for US merchants in March 2026.

**Goal:** a conformant `complete` that places a real `Order`, redeems the
delegated payment token through the existing Stripe integration, records
delegation evidence for disputes, and stays disable-safe/fail-soft.

## Non-goals

- UCP checkout binding (rides on this later), AP2 verifiable-credential
  verification, stablecoin rails (anti-bets/later per the roadmap).
- Live end-to-end smoke against OpenAI's production agents — requires
  enrollment in Stripe's agentic-commerce program; this slice ships
  spec-conformance + Stripe-mocked integration tests and a manual-gateway
  test path. Live smoke is a follow-on once program access exists.
- Dashboard "agent orders" reporting UI (evidence lands on the Order now;
  a dedicated surface is a later slice).

## Design

### 1. `complete_checkout_session` (the money path)

Request body per ACP spec: `{ "payment_data": { "token": "spt_…", "provider":
"stripe" }, "buyer": {…}? }`. Flow, all inside the existing view skeleton:

1. Auth: existing `require_acp_scope` (Bearer + `acp.checkout`).
2. Load cart (`_get_cart`); validate: not expired/canceled, has items, has
   email + shipping address (accumulated by `update` calls); else ACP
   `MessageError` (`invalid`/`missing`, param-scoped) under 422.
3. Validate `payment_data`: `provider == 'stripe'` and a non-empty `token`;
   unsupported provider → `unsupported` 422 (unchanged behavior when the
   payments plugin/gateway is unavailable).
4. **Order:** `OrderService.create_from_cart(cart, email, shipping_address,
   billing_address)` — the same call the storefront checkout uses (totals,
   coupons, shipping, tax all identical).
5. **Payment:** new `redeem_delegated_token(order, token)` classmethod in
   `plugins/installed/payments/services/stripe.py` — `PaymentIntent.create`
   with `amount/currency` from the order, `payment_method=token`,
   `confirm=True`, `off_session=True`, `idempotency_key=f'acp-{cart.id}'`,
   `metadata={'order_id', 'acp_session': str(cart.id)}`; records the
   `PaymentTransaction` (`provider='stripe'`, status per intent outcome) —
   mirroring `create_payment_intent`'s shape. Declines/StripeErrors return
   `{'success': False, 'error', 'decline_code'?}` — never raise.
6. On success: `order.payment_status='paid'`; fsm-confirm the order the same
   way the Stripe webhook success path does (reuse its helper); fire nothing
   extra (ORDER_PLACED hooks already fire inside `create_from_cart`).
7. On decline: order is NOT left dangling — cancel it (or leave `pending
   payment_failed` if that's the webhook path's convention; match it) and
   return ACP `payment_declined` `MessageError` under 422.
8. **Evidence:** `order.metadata['acp'] = { 'api_version': ACP_API_VERSION,
   'session_id': str(cart.id), 'token_fingerprint': sha256(bearer)[:16],
   'spt_last4': token[-4:], 'completed_at': iso8601, 'user_agent':
   request.META['HTTP_USER_AGENT'][:300] }` and `order.source = 'agent:acp'`
   (fits the existing `source` CharField(50) convention `web/api/pos`).
9. Response: 200 `CheckoutSessionWithOrder` — `serialize_session(...)` plus
   `order: { id, checkout_session_id, permalink_url }` per spec; status
   `completed`.

### 2. Per-product eligibility

`is_eligible_checkout` in the agent feed (`feed.py`) and a guard in
`create_checkout_session`: a product carrying metafield
`agentic.exclude == true` (namespace `agentic`, key `exclude`, boolean) is
omitted from the feed's checkout-eligible flag and rejected at session-create
with an item-scoped `MessageError`. Read via the metafields plugin
(fail-soft: metafields disabled → everything eligible). No model changes.

### 3. Config

`get_config_schema` gains `payments_enabled` (boolean, default `false`,
title "Accept agent payments (ACP complete)") — the money path returns the
Phase-1 `unsupported` message until the merchant flips it. Master `enabled`
switch unchanged. `app.py` version bump 0.x → next minor.

## Contract & safety notes

- agentic_checkout already `requires` orders/catalog/inventory/agent_mcp;
  payments is consumed via lazy import + fail-soft (`unsupported` when
  missing) — matching how storefront checkout treats gateways, and keeping
  the plugin disable-safe (payments off → conformant 422, never a 500).
- No cross-plugin model imports beyond the already-declared deps; the
  payments call goes through the service layer, not the gateway registry
  (Stripe-only by spec — SPT is a Stripe primitive).
- Idempotency: `complete` retried by an agent must not double-charge —
  the Stripe idempotency key is derived from the cart id; a second call on
  an already-completed session returns the completed session (200) without
  a new intent (check `order` existence for the cart first).

## Verification

- Unit/conformance (extend `tests/test_acp.py`): complete without
  `payments_enabled` → 422 unsupported (Phase-1 behavior preserved);
  complete with mocked Stripe success → 200, `CheckoutSessionWithOrder`
  shape, Order exists with `source='agent:acp'`, `payment_status='paid'`,
  evidence metadata present, PaymentTransaction recorded; mocked decline →
  422 `payment_declined`, no paid order; retry after success → 200 same
  order, no second PaymentIntent call; under-scoped token → 403; ineligible
  product at session-create → item error.
- Stripe is mocked at the `stripe.PaymentIntent` boundary (same style as
  existing payments tests); no live calls in CI.
- Suites: `DATABASE_URL='sqlite:///:memory:' python manage.py test
  plugins.installed.agentic_checkout plugins.installed.payments
  plugins.installed.orders` green; ruff clean; zero migrations.
