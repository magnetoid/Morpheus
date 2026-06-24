# ACP (Agentic Commerce Protocol) — agent-driven checkout — spec

Status: **draft for review** (grounded in the real ACP `2026-04-17` spec; no code
yet). Lets AI agents (ChatGPT Instant Checkout et al.) discover our products and
complete a purchase against our own Stripe account via a delegated **Shared
Payment Token (SPT)**. Maintained by OpenAI + Stripe; **beta**.

Source of truth for shapes: `github.com/agentic-commerce-protocol/agentic-commerce-protocol`
`spec/2026-04-17/openapi/openapi.agentic_checkout.yaml` (+ `openapi.delegate_payment.yaml`,
`openapi.feed.yaml`). Pin the dated version — ACP ships breaking versions
(`2025-09-29` → `2026-04-17`); the merchant echoes the one it implements in the
`API-Version` response header.

## Anchoring decisions
1. **A new plugin, `plugins/installed/agentic_checkout/`.** Not bolted onto
   `agent_mcp` (keeps the disable-test clean; ACP is its own protocol surface).
   It **contributes** to existing surfaces, owning no duplicate commerce logic.
2. **~80% reuse.** Discovery reuses `agent_mcp`'s `/.well-known/` mounting +
   Bearer/scope auth; the checkout session is backed by our existing **`Cart`**;
   completion reuses **`OrderService.create_from_cart()`**; pricing reuses the
   **`CART_CALCULATE_BREAKDOWN`** hook; availability reuses **`inventory.StockLevel`**.
   The only genuinely new code is the SPT→PaymentIntent redemption.
3. **OFF by default.** Registered in `MORPHEUS_DEFAULT_PLUGINS` but disabled until
   a merchant enrolls in Stripe ACP. **The money path (`complete`) must not be a
   live, untested charge path** — it can't be verified end-to-end without a Stripe
   ACP enrollment + a real agent, so it ships behind the disable + a settings flag
   and is unit-tested with a mocked Stripe.

## The five endpoints (we are the *server*; the agent calls us)
All under a plugin-owned prefix (proposed `"/acp/"`), Bearer-authenticated:

| Method + path | operationId | Backed by |
|---|---|---|
| `POST /acp/checkout_sessions` | createCheckoutSession | new `Cart` + breakdown |
| `POST /acp/checkout_sessions/{id}` | updateCheckoutSession | mutate the `Cart` |
| `GET /acp/checkout_sessions/{id}` | getCheckoutSession | read the `Cart` |
| `POST /acp/checkout_sessions/{id}/complete` | completeCheckoutSession | SPT redeem + `OrderService.create_from_cart` |
| `POST /acp/checkout_sessions/{id}/cancel` | cancelCheckoutSession | release `Cart` reservation |

**Required request headers** (parsed + echoed where ACP requires): `Authorization`
(Bearer), `API-Version`, `Idempotency-Key`, `Request-Id`, `Signature`, `Timestamp`,
`Accept-Language`. **Idempotency** is mandatory on the mutating calls
(create/complete) — key off `Idempotency-Key` so a retried complete never
double-charges (mirror the `ORDER_PAID`-once gate already in payments). **Signature**
verification (HMAC over body+timestamp, agent's key) gates inbound authenticity.

## Data mapping — ACP `CheckoutSession` ⇄ our `Cart`/`Order`
The session **id is the `Cart` id**. We shape a conformant `CheckoutSession`
response from the cart:

- `status` (ACP 11-state enum) ← derived: empty/invalid → `not_ready_for_payment`;
  priced + address set → `ready_for_payment`; post-complete → `completed`;
  canceled → `canceled`; expired cart → `expired`.
- `line_items[]` ← `CartItem`s → ACP `LineItem` (`id`, `item{id,name,unit_amount}`,
  `quantity`, `sku`, `product_id`, `variant_id`, `availability_status` from
  `StockLevel`, per-line `totals[]`). Amounts are **integer minor units** (ACP) —
  convert from our `Money` cents carefully (djmoney is already cents-quantized).
- `totals[]` ← the `CART_CALCULATE_BREAKDOWN` dict → ACP `Total` rows
  (`items_base_amount`, `subtotal`, `discount`, `fulfillment`, `tax`, `total`),
  each `{type, display_text, amount}`.
- `fulfillment_options[]` ← our shipping-rate options; `selected_fulfillment_options`
  ← the chosen rate stored on `cart.metadata`.
- `buyer` ← `Buyer{email*, first/last_name, phone}`; `fulfillment_details.address`
  ← ACP `Address{name, line_one, line_two, city, state, country, postal_code}` →
  our address JSON.
- `messages[]` ← `MessageInfo`/`MessageError` (codes: `out_of_stock`, `low_stock`,
  `payment_declined`, `coupon_invalid`, …) for any validation/availability issue.
- `links[]` ← `terms_of_use`/`privacy_policy`/`return_policy`/… from CMS/settings.
- `currency`, `created_at`, `updated_at`, `expires_at`, `continue_url` (a storefront
  cart URL).

## Completion + Shared Payment Token (the one new piece)
`completeCheckoutSession` body: `{ buyer?, payment_data* }`. The SPT arrives inside
`payment_data` (`handler_id` + `instrument`/billing_address). Redemption (merchant
uses **its own** Stripe account):

1. Validate the session is `ready_for_payment`; re-price; re-check stock.
2. `OrderService.create_from_cart(cart, email, shipping, billing)` → `Order`
   (atomic; fires `order.placed`; reserves inventory) — **unchanged path**.
3. **New:** `payments/services/delegated_payment.py::complete_with_shared_token(order, token)`
   → create a Stripe `PaymentIntent` with `payment_method=<spt>`, `confirm=True`,
   `off_session=True`, amount = order total, idempotency-keyed on the ACP
   `Idempotency-Key`. On success record the `PaymentTransaction`, mark the order
   paid, fire `ORDER_PAID` (commits inventory, mints digital tokens, emails — all
   existing subscribers).
4. Return `CheckoutSessionWithOrder` (`status='completed'` + `order{ id,
   permalink_url, order_number, totals }`). On decline → `MessageError`
   `payment_declined` and `status` back to `ready_for_payment`.

The SPT is **single-use, amount-scoped, time-boxed, seller-scoped** (Stripe issues
it via `delegate_payment` on the *agent's* side; we only redeem). We store **no**
card data — Stripe is the vault. The token is never logged or surfaced to the
assistant.

## Discovery: `/.well-known/acp.json`
Mirror `agent_mcp/well_known.py` (which already serves `ucp.json` + `agent.json`):
advertise `protocolVersion`, the checkout base URL, the product-feed URL, supported
`capabilities` (payment handlers = stripe SPT), and the Bearer `auth`
registration. Add an `acp.checkout` scope to `agent_mcp`'s `AVAILABLE_SCOPES`.

## Product feed (`openapi.feed.yaml`)
Reuse `google_shopping`'s `map_product()` logic, re-shaped to ACP feed fields
(id, title, description, link, image_link, price/currency, availability, gtin,
brand, item_group_id for variants). Serve at a plugin URL; advertise it in
`acp.json`. (Can land in Phase 1 — it's read-only and fully testable.)

## Auth & safety
- Reuse `agent_mcp` Bearer tokens + `scopes.py`; require `acp.checkout` (+
  `catalog.read` for the feed). New synthetic-service-user path already exists.
- Every completed order tagged `order.metadata.agent_id` + `core.audit` `acp.*`
  events (mirrors the Trusted-Agent persistence already declared in `agent.json`).
- Signature + timestamp window (reject stale) on inbound; idempotency on mutating.
- Rate-limit create/complete per token (reuse `core/utils/rate_limit`).

## Phases (each independently verifiable)
1. **Discovery + read/quote half (testable, no live Stripe).**
   `agentic_checkout` plugin scaffold; `/.well-known/acp.json`; the ACP **product
   feed**; `createCheckoutSession` / `getCheckoutSession` / `cancelCheckoutSession`
   backed by `Cart` with a **conformant `CheckoutSession`** response; `updateCheckoutSession`
   for line-item/fulfillment edits; Bearer/scope auth; OFF by default.
   *Verify*: unit tests build a session from a cart, get/cancel, conformant JSON
   shape (validate against the json-schema), availability + totals correct;
   permission-boundary (no token / wrong scope / valid scope); disable test.
   `complete` returns a conformant `MessageError unsupported` until Phase 2.
2. **The money path (needs a Stripe ACP enrollment).** `delegated_payment.py`
   SPT→PaymentIntent redemption; `completeCheckoutSession` → order + charge +
   `ORDER_PAID`; idempotency/signature hardening; `acp.*` audit + `agent_id`
   tagging. *Verify*: complete creates an order and charges via a **mocked**
   Stripe SPT (real interface, mocked transport); idempotent double-complete
   charges once; decline path returns `payment_declined`. Live smoke deferred to
   a real Stripe ACP sandbox.
3. **Polish.** Webhooks (`openapi.agentic_checkout_webhook.yaml`) for async order
   status back to the agent; affiliate attribution; fulfillment groups; version
   negotiation across `2025-09-29`/`2026-04-17`.

## Forks (recommendation in bold)
- **Packaging:** **new `agentic_checkout` plugin** vs. extend `agent_mcp`.
- **Order path:** call **`OrderService.create_from_cart()` directly** vs. wrap the
  `complete_order` GraphQL mutation. (Direct = fewer layers; the GraphQL mutation
  itself just wraps the service.)
- **SPT redemption home:** **new `payments/services/delegated_payment.py`** vs. a
  method on `stripe_gateway`. (Isolated = the delegated flow is testable + doesn't
  touch the normal intent path.)

## Non-goals (this iteration)
- Non-Stripe PSPs (ACP allows any compatible PSP; we ship Stripe SPT only).
- The agent-side `delegate_payment` mint (that's the PSP's job, not the merchant's).
- B2B `payment_terms` (net_30 etc.), split payments, gift wrap — declared in the
  schema, deferred.

## Success criteria
- An ACP agent can discover the feed + `acp.json`, create a checkout session from
  SKUs, get a conformant priced session with real availability, and cancel it —
  all Bearer-scoped, OFF unless enabled (Phase 1).
- With Stripe ACP enabled, `complete` with an SPT creates a paid order exactly once
  (idempotent), fires `ORDER_PAID`, tags `agent_id`, and audits `acp.*`; declines
  surface as `payment_declined` (Phase 2).
- Disabling `agentic_checkout` removes the manifest, feed, and endpoints; no core
  or sibling surface references it.
