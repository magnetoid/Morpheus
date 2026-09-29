# Commerce flow and stability plan (2026-09)

Status: PLAN, 2026-09-28, awaiting the owner's go-ahead.

Evidence:
- The code was traced three ways (purchase path, features around it, bookings plus
  merchant operations) and each top claim re-checked by hand.
- A read-only snapshot of all three live stores, and live page checks.

## Context

The owner asked for a deep analysis of Morpheus's e-commerce features and flows: what
works, what doesn't, and a plan to make shopping work end to end and stay stable.

**Bottom line:** the money logic inside the engine is mostly sound, but the stores can't
reliably sell:
- On dotbooks and supernatural, **checkout pre-selects Stripe, which has no keys**, so a
  shopper who doesn't switch to cash on delivery hits an error after the order is
  created.
- No store has shipping or tax rates.
- Nothing tracks stock.
- Several features look finished and do nothing.
- Merchants lack basic tools: no "shipped" email, Export gives the wrong file, and
  montenegro has no enquiry inbox.

Almost nothing has exercised this in production: since July there have been 8 dotbooks
orders, 7 of them staff tests.

## Owner decisions (2026-09-28)
- **Payments:** offer all of cash on delivery, Stripe, PayPal and a local card
  processor. PayPal is already built and needs only credentials; a local processor is
  new work.
- **Currency:** USD on all three stores.
- **Stock:** no stock limits, so turn tracking off.
- **Urgent:** turn off Test payment on supernatural. **Done 2026-09-28**: the checkout
  picker now offers bank transfer, Stripe and cash on delivery, and a request naming
  `test` is rerouted server-side.

## Live state (read-only snapshot)

| | dotbooks | supernatural | montenegro |
|---|---|---|---|
| Orders ever | 8 (7 staff tests); all `unpaid`, even delivered | 0 | 0 (booking app) |
| Checkout offers | bank transfer (no bank details), **Stripe (default, no keys)**, cash on delivery | same (Test payment now off) | enquiry only |
| Shipping | 1 zone, **0 rates** → always free | none → free | — |
| Tax | 0 rates; provider `stripe`, no keys | none | — |
| Stock records | 0 (999 products "tracked") | 0 (504 "tracked") | — |
| Catalogue | 861 active | 684 active, **18 at $0 and buyable** | 142 services, 100 properties |
| Store settings | currency `$`, timezone `+1` | currency `$`, country `sr` | USD / US |
| Bookings | — | — | **25 enquiries (Aug–Sep, 21 people) never seen**; 16 old free bookings, all in the past |
| Monitoring | none; logs vanish on every deploy | same | same |

## What works (verified)
- **One order and payment path.** `/checkout/`, `/checkout/quick/` and agentic checkout
  all use `completeOrder` → `create_from_cart` inside a single database transaction.
- **Prices:** the price seam covers both display and charge, and the cart breakdown runs
  in the documented order: promotions → tax → shipping → member → loyalty → gift card →
  eco.
- **Discounts and tenders:** coupons, promotions, gift cards and loyalty (with re-credit
  on refund), and the member discount.
- **Stock reservation**, whenever a stock record exists, with expiry of unpaid orders
  under a row lock.
- **Stripe:** PaymentIntent, a single idempotent webhook path, `ORDER_PAID` fired once.
  **PayPal:** capture plus a webhook backstop.
- **After payment:** emails (from 2026-09-28), download links for digital products,
  stock committed.
- **Bookings:** availability, quote and capacity locking; enquiry emails.
- **Merchant orders:** list, detail, cancel, partial refund with an over-refund guard.
- **Themes:** all three ship the full shopping template set.
- **Tests:** `orders/tests/test_checkout.py::CheckoutFlowTests` is a strong end-to-end
  suite.

## What is broken

### Checkout and money (customers hit these)
| # | Defect | Evidence |
|---|---|---|
| B0 | Unconfigured gateways are offered, and Stripe is the default: `is_enabled()` treats a missing config row as enabled, `default()` prefers Stripe, and `create_payment_intent` has no "keys present?" check. Bank transfer is offered with no bank details | `payments/models.py:156-166`, `payments/gateway.py:75-90`, `payments/services/stripe.py:148-184`, `storefront/views/checkout_one_page.py:296` |
| B1 | Tax reads `address['region']` but checkout sends `state`, so state rates never apply | `tax/app.py:44` vs `checkout_one_page.py:222`, `orders/graphql/mutations.py:572` |
| B2 | "Prices include tax" is saved and never read | `tax/dashboard.py:144` is the only use |
| B3 | 18 active $0 products can be bought (supernatural); nothing prevents it | live |
| B4 | The tree offset ($1.50) is in the total but never shown on the order, confirmation page or emails | eco_impact templates only in cart/dashboard |
| B5 | The AI shopping concierge's cart tool fails every time with `FieldError` (`Cart.status` doesn't exist) and bypasses the price seam | `agent_core/tools/cart.py:8-24` (reproduced) |
| B6 | Draft-order conversion skips the breakdown, tax, stock reservation, `ORDER_PLACED`/`ORDER_PAID` and all emails | `draft_orders/services.py:36-72` |

### Merchant operations
| # | Defect | Evidence |
|---|---|---|
| B7 | No "shipped" email: fulfil defaults to `mark_shipped`, skipping `fulfilled`, and no `ORDER_SHIPPED` event exists | `admin_dashboard/forms/orders.py:99-103` |
| B8 | Dashboard refund bypasses `RefundService` (lock and idempotency), so a double click can refund twice | `admin_dashboard/forms/orders.py:47-74` vs `orders/refunds.py:121-197` |
| B9 | "Mark paid" sets `payment_status` but never confirms the order (it stays `pending`); delivered cash-on-delivery orders are never prompted | `admin_dashboard/views_split/orders.py:240-257` |
| B10 | Orders → Export exports products | `admin_dashboard/views_split/orders.py:434` |
| B11 | No staff-notes UI and no invoice/print | `order_detail.html` |
| B12 | Bookings: enquiry status can never change, there is no operator inbox, stays have no screen at all, booking confirmations send no email, and there is no cancel or refund | `booking_marketplace/host.py`, `dashboard.py`, `email.py:_host_recipient` |
| B13 | Montenegro shows a dead cart icon and "Shop" link; its sign-in code pages are unbranded | `themes/library/montenegro/` |

### Features that look finished and do nothing
- **Five default-on apps.** `save_for_later`, `rich_post_purchase`,
  `post_checkout_upsell`, `one_click` and `referrals` have buttons and settings but no
  views, URLs, services or hooks.
- **The loyalty app's referral engine** has no caller.
- **Stock.** No dashboard or importer can create a stock record (only the AI tool and
  GraphQL), so "Track inventory" is cosmetic.
- **Store credit** can be issued but never spent (`orders/store_credit.py:62`).
- **Markets and channel prices** are never used for the charge. Of the three
  per-market price stores, only `localized_prices` counts.
- **B2B price lists** apply only to CSV reorders.
- **A guest's orders** never attach to the account they create later.

## Plan

Each release goes through `manage.py release`, the full test suite, a deploy to all
three stores, and a live check.

### Release 1 status (v0.75.23)
Done:
- **Payment options:** only set-up gateways are offered; the default is a working
  method; the sandbox is staff-only; Stripe's error text is hidden; checkout uses one
  publishable-key helper.
- **Tax:** state rates apply (the `state`/`region` fix), region matching ignores case,
  and the dead "Stripe Tax" and "Prices include tax" controls are removed.
- **$0 guard:** the cart refuses a $0 product and the page reports it out of stock.
- **Tree offset:** a named "Plant a tree" line appears on the order, the email and the
  dashboard; the email now shows discounts.
- **Mark paid** confirms the order, and the order list shows an awaiting-payment
  banner.
- **Found in this release: order emails had never rendered.** `core/emails/templates`
  was on no loader path.

Deviations from the plan:
- **Tax-inclusive pricing is deferred.** It needs every breakdown handler plus the
  theme and email labels, and no store has tax rates. The dead toggle was removed
  instead of leaving a control that does nothing.
- **"Tidy store settings" was dropped.** `primary_currency` and the timezone field
  have no consumer, so changing them does nothing.

### Release 1 — every checkout can take money correctly
1. **Payment options (B0).** Offer a gateway only when it's configured: Stripe with
   keys, PayPal with credentials, bank transfer with bank details. Default to the first
   configured one; with none of those set up, that's cash on delivery. The payment step
   refuses an unconfigured gateway with a clear message, never a raw Stripe error. Test
   payment is offered to staff only.
2. **Tax (B1, B2).** Read `state` as well as `region`, and honour "prices include tax"
   by extracting tax rather than adding it. Also fix dotbooks' tax provider setting
   (`stripe` without keys).
3. **$0 guard (B3).** An active product at price 0 can't be added to the cart unless it
   is explicitly marked free.
4. **Tree offset (B4)** appears as a line on the order, the confirmation page and the
   emails.
5. **Mark paid (B9)** also confirms the order. The dashboard shows delivered-but-unpaid
   cash-on-delivery orders.
6. **Stock (owner: no limits).** Turn `track_inventory` off on all products on all three
   stores. Tidy store settings: currency `USD`, valid timezones.
7. **Tests.**
   - One test per item above.
   - A checkout test that reconciles every total line (subtotal + shipping + tax −
     discount + extras = total).
   - A gateway-offer test (unconfigured gateways never appear).
   - A tax-through-the-pipeline test with a state address.
8. **Live.** One staff purchase per selling store, paid by cash on delivery: order,
   emails, dashboard state.

### Release 2 status (v0.75.24)
Done:
- **Shipping:** shipping straight from processing now fulfils the order: the "on its
  way" email with tracking, post-purchase follow-ups and webhooks. None had fired
  for any shipped order.
- **Refunds:** the dashboard refund goes through `RefundService`, which now locks the
  order and logs to the timeline.
- **Orders:** a real CSV export (list filters, selected orders, formula-safe); staff
  notes and the customer's note on the order page; the address shown as lines; a
  printable invoice.
- **Montenegro:**
  - an Enquiries inbox (experiences and stays, new/contacted/closed, reply by email)
    and a Stays screen;
  - host alerts reply to the guest and fall back to the store contact email;
  - stay enquiries confirm to the guest;
  - booking confirmation emails are wired for when payments are on;
  - the cart icon shows only when the cart has items;
  - the sign-in code pages are branded.
- **AI concierge:** the cart tool goes through `CartService`.

Note: the invoice shows the store name, email and phone. A legal invoice also needs
a business address and tax ID, which StoreSettings doesn't have.

### Release 2 — merchants can run the shop
1. **Shipped email (B7):** an `ORDER_SHIPPED` event with the tracking number.
2. **Refunds (B8)** go through `RefundService`.
3. **Real order CSV export (B10).**
4. **Staff notes and a printable invoice (B11).**
5. **Montenegro operator inbox (B12):**
   - enquiries and stay enquiries: status new → contacted → closed, with a reply link;
   - a stays bookings screen;
   - alerts to `BOOKING_ENQUIRY_NOTIFY_EMAIL` or the store's contact email;
   - booking confirmation emails, ready for when payments are enabled.
6. **Montenegro cleanup (B13):** remove the cart and Shop leftovers; brand the sign-in
   code pages.
7. **AI concierge cart tool (B5):** route through `CartService`.

### Release 3 — real online payments (needs credentials from the owner)
1. **Stripe:** the owner provides keys from an eligible entity. Register the webhook and
   verify with one low-value live purchase and a refund.
2. **PayPal:** business credentials plus the webhook, then the same live check.
3. **Local card processor:** the owner picks one (e.g. Monri, AllSecure) and gets a
   merchant account. Build it as a gateway following the `advanced_payments` pattern
   (`gateway_registry`), with a webhook and refunds.
4. **Bank transfer:** add bank details, or leave it off.

### Release 4 status (v0.75.25)
Done:
- **Inert apps:** save_for_later, one_click, referrals and rich_post_purchase ship off
  (`enabled_by_default = False`) and are switched off on the three live stores. The
  referrals block had promised "Give $5, get $5".
- **Upsell trimmed:** post_checkout_upsell keeps its working receipt suggestion and
  loses the dead in-checkout button and its dead settings.
- **AI agent runs retired:** the agent runs on order placed, customer registered,
  cart abandoned and product created are gone. So is the orphaned AgentOperator
  (plugin-boundary baseline 118 → 117). Descriptions stay on request in the product
  editor.
- **Guest orders** link to an account on `CUSTOMER_EMAIL_VERIFIED` (a new event
  produced by the sign-in code and by allauth email confirmation), never at signup.
- **Draft conversion** keeps the quoted prices but reserves stock (refusing if
  short), fires ORDER_PLACED, and converts once (row lock).
- **Store credit** is a checkout tender (@46): debited on order, re-credited in
  full on cancel and pro rata on refund, idempotent and capped.

Deferred to a later release:
- **The three per-market price stores and B2B price lists in the price seam.**
  Every store is USD with no markets or B2B in use.
- **Stock quantities in the editor and importer.** The owner chose no stock limits.

### Release 4 — finish or retire half-built features
1. **Inert apps:** take the five out of `MORPHEUS_DEFAULT_APPS` (or disable them per
   store) until they're built.
2. **Draft orders (B6)** go through `create_from_cart` (or reserve and fire the events).
3. **Store credit** becomes a cart tender (priority ~46).
4. **Guest orders** link to the account on sign-up.
5. **Pricing:** one per-market price store (`localized_prices`); wire B2B price lists
   into the price seam.
6. **Platform:** stock quantities editable in the product editor and the CSV importer,
   for stores that do track stock.

### Release 5 status (v0.75.26)
Done:
- **The error log now emails people.** Errors had been captured all along
  (`core/errors`, `ErrorEvent`, `/dashboard/errors/`, surviving deploys) and told
  nobody: supernatural's product pages returned 500 from Sep 12 to Sep 22
  unnoticed.
  - A **daily digest** of server errors at 06:30 UTC.
  - A **nightly health check** at 05:00 UTC. Core checks email setup and the
    templates; payments, orders, storefront and booking each contribute their own
    via `HEALTH_CHECKS`. A failure is recorded and emailed at once.
  - Alerts go to `ERROR_ALERT_EMAILS`, else the superusers, else the contact
    email.
- A **checkout test under every theme**.

Changed from the plan:
- **No synthetic purchase with a real order each night.** It would create fake
  orders, or push fake purchases to GA4 and ad platforms through ORDER_PLACED
  subscribers. The health check instead prices a real cart inside a rolled-back
  transaction and loads the purchase pages over HTTP.
- **No CI browser test.** GitHub Actions is billing-blocked, so it would never
  run; the Django-level theme test runs in every suite.
- **Sentry stays optional.** It is already wired and turns on when `SENTRY_DSN`
  is set.

Found while verifying Release 5 (fixed in v0.75.27):
- **Every job scheduled in `morph/celery.py` had never run.** An
  `app.conf.beat_schedule` assignment was replaced when Celery loaded its config
  from settings. The affected jobs were the error-log prune, the update check, the
  outbox drain, the daily briefing, and the new health check and digest. They now
  go into `settings.CELERY_BEAT_SCHEDULE`.

Follow-up, done 2026-09-29:
- **dotbooks' 50,962 PENDING `OutboxEvent` rows are deleted.** They dated from
  2026-04-26 to 2026-07-12. The table was not growing: since 79c4cfa2 (2026-07-12)
  `core/hooks.py` writes outbox rows only when `NATS_URL` is set, and no store sets
  it. The rows had no reader: the drain skips without NATS, and the observability
  rollup reads only the last 6 hours. They were removed after that night's backup.
  The other two stores had none.

Found while doing it (not fixed):
- **`/healthz/deep`'s outbox check has never checked anything.** It filters on
  `sent_at`, which `OutboxEvent` does not have. The `FieldError` is caught and the
  check reports `ok` with "unavailable".
- **The observability rollup has had no input since 2026-07-12.** It builds
  `MerchantMetric` from outbox rows, which stopped being written without NATS. Its
  only reader is the GraphQL `metricSeries` field, and nothing in the dashboard
  calls it. Either feed it from the hooks directly or retire it.

### Release 5 — stay stable
1. **Error tracking** (Sentry or self-hosted GlitchTip) on web and worker, with alerts on
   5xx and failed tasks. Keep logs across deploys.
2. **A nightly synthetic purchase** per selling store: staff test payment → order →
   email → cancel, alerting on failure.
3. **A CI browser test** of checkout for each theme.

## Still open with the owner
- **Shipping rates** per store. Today shipping is free everywhere by default.
- **Supernatural's 18 products at $0.** Price them, or let Release 1's guard hide them.
- **Montenegro's 25 unanswered enquiries.** The owner can read them in the database via
  staff, or Release 2's inbox will list them.
- **Stripe and PayPal credentials**, and the choice of local processor (Release 3).

## Verification
- **Per release:** the targeted tests plus the full suite
  (`DATABASE_URL='sqlite:///:memory:' MORPHEUS_EXTRA_APPS=plugins.installed.booking_marketplace manage.py test`),
  `ruff check .`, template compile, `release --check`.
- **Live after each deploy:**
  - `/readyz` shows the new version.
  - The checkout picker offers only configured gateways.
  - A staff cash-on-delivery purchase reconciles its totals and sends its emails.
  - Dashboard actions (mark paid, fulfil → shipped email, refund) work end to end.
  - Montenegro: an enquiry shows up in the inbox and its status can change.
