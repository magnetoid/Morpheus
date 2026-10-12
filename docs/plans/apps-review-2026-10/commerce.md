# Commerce cluster review: checkout, orders, marketing, money, shipping (27 apps)

Method: read every app's `app.py`, models, views, hook registrations and templates; checked consumers with grep; printed the assembled Celery beat schedule (`django.setup()` + `morph.celery`); checked dotbooks.store live with a real cart (checkout page and review step). Rows are from facts.json, in the order dotbooks/supernatural/montenegro/irving. All paths are relative to `plugins/installed/` unless noted otherwise.

## Summary table

| app | what it really does today | real/stub | verdict | key improvements |
|---|---|---|---|---|
| checkout_experience | Puts a **second, unstyled checkout form** (email, full address, "Pay USD 0") under the theme's real checkout on all 4 stores, and loads `checkout.js` on every page of every store. The JS posts `completeOrder` and then redirects to `/orders/<n>/confirmation/`, a route that does not exist. No express pay, no autocomplete, no layouts. | harmful stub (active on all 4 stores) | **delete** | Remove now. Checked live on dotbooks: a digital-only cart's checkout says "No shipping address needed", and below it this form asks for a shipping address. |
| one_click | One model (`OneClickToken`) and a button template. Nothing mints a token, and the mutation and `ONE_CLICK_KEY` don't exist. | stub, off on all stores | **delete** | Drop the table (0 rows). |
| post_purchase | ORDER_PLACED/ORDER_FULFILLED create `JourneyStep` rows (tracking, delivered, review request, NPS); a task sends plain-text emails; there is an NPS form and an NPS report card. **Nothing schedules `post_purchase.process_due_steps`**, so the queued steps (11 rows on dotbooks, 2 on supernatural) never send. | real but inert | keep; **absorb post_checkout_upsell** | Register the beat entry. Tag the hooks with the app as owner. Drop `tracking_sent`, which duplicates orders' ORDER_FULFILLED "on its way" mail. Add a tool for NPS results. |
| rich_post_purchase | One model (`ChannelPreference`); nothing reads or sends through it. | stub, off on all stores | **delete** | Multichannel belongs in notifications if it is ever built. |
| post_checkout_upsell | One block on the order receipt: the merchant's chosen product slug, or failing that **the newest active product** (not a recommendation). | real, tiny | **merge into post_purchase** | Use personalisation co-purchases instead of "newest". Its settings card sits under "payments". |
| cart_abandonment | Beat scans stale carts, fires CART_ABANDONED, and sends a consent-checked 3-step recovery drip (the only recovery sender). | real, 32 tests | keep | Add an agent tool (abandoned carts, drip stats, pause). Rows 0 means no store has ever sent a recovery email; check SMTP and consent on the live stores. |
| marketing | Owns the `Coupon`/`CouponUsage` tables (the coupon CRUD lives in the **admin_dashboard shell**, and the coupon *math* lives in **promotions**), `EmailCampaign` (used only by newsletter), and a `Redirect` model that **duplicates `seo.Redirect`**. Its own dashboard views are shadowed by admin_dashboard routes. The GraphQL modules are empty files. The manifest claims "discount engine, abandoned-cart recovery", and it does neither. | data-holder shell, 0 tests, 0 rows | **dissolve**: Coupon to promotions, EmailCampaign to newsletter, Redirect deleted | See M1. |
| promotions | Rule engine (percent/fixed/free-ship/bogo/tiered/gift) at CART_CALCULATE_BREAKDOWN priority 10, **plus the whole marketing.Coupon evaluation**. The dashboard is a read-only table ("create one via Linda or the Django admin"). | real engine, thin UI | keep, **becomes the single discounts app** | Give it a create/edit UI. Add `@require_capability`. Add coupon tools. Test `evaluate()` (2 tests, both staff-gate). Implement or remove `gift` and coupon `buy_x_get_y`. Delete the dead `on_cart_total`. |
| gift_cards | Issue/redeem/audit with an append-only ledger; tender at priority 50; re-credits on cancel and refund; issues purchased cards on ORDER_PAID. | real, 18 tests | keep | The apply/remove routes live in the storefront shell, and the theme hardcodes the "Have a gift card?" form with no `{% plugin_enabled %}`, so the form survives a disable. Add a void/adjust tool. |
| loyalty_points | Earns points on ORDER_PAID, redeems at priority 45 (`/checkout/points/apply/`, cart block), shows an account page, re-credits on refund. **Also dead weight:** a `Referral` model and service nothing calls, tiers and RFM tasks that are never scheduled, and a `CustomerRFM` that duplicates `customers.rfm`. | real core and dead extras, 59 tests | keep; **shed the referrals, tiers and RFM code** | Tag both hand-registered hooks. Fix the stale docstring that says redemption is "deferred". 0 rows on all stores, so the ledger is unproven in production. |
| referrals | Two models plus an account block promising "Give $5, get $5". Nothing issues links or credit. A second, also-dead referral implementation sits inside loyalty_points. | stub, off on all stores | **delete** (rebuild on affiliates if wanted) | See M9. |
| newsletter | Subscribers with double opt-in, signup popups, chunked campaign send, unsubscribe. In use (27 and 22 rows). | real, 50 tests | keep; **takes over EmailCampaign** | `requires = ['marketing']` exists only for `EmailCampaign`. No agent tool to create or send a campaign (only stats, list, popups). |
| affiliates | Full affiliate programme: links, clicks, conversions, payouts, creatives, widgets, partner portal, GraphQL. | real, 4.9k LOC, 88 tests | keep (consider opt-in: used only on dotbooks, 4 rows) | `AffiliateLink.coupon_code` must match a marketing.Coupon the merchant creates separately; nothing links the two. |
| returns_portal | Two models (`ReturnResolution`, `ReturnFeedback`) that **nothing writes**. What actually works: the `return_window_days` setting published as JSON-LD `MerchantReturnPolicy`, and an account CTA. The return flow itself is orders plus the storefront shell. | mostly stub | **merge into orders** | The window is **published but never enforced** (`orders/refunds.py:213`). The CTA promises exchanges "ship within 48 hours". `requires loyalty_points`, but it is unused. |
| draft_orders | Staff-built drafts with lines that convert to a real Order (stock reserve and ORDER_PLACED included). In use (2 and 1 rows). | real, 4 tests | keep; **absorbs b2b quotes** | Add a `draft_orders.create` tool (only list and convert exist). |
| subscriptions | Plans, subscriptions, invoices, dunning and renewal beat, Stripe billing adapter, member discount at priority 40, PDP subscribe-and-save, footer "Membership" link. | real, 109 tests, 0 rows anywhere | keep but **opt-in** | The footer link is unconditional: live `/membership/` on dotbooks is an **indexable 200 saying "No membership plans are available right now"** (a soft 404 on every store). Add a `subscriptions.create_plan` tool. Priority 40 ties with `functions`. |
| digital_products | Issues `DownloadToken`s on ORDER_PAID, serves token-protected downloads, adds a Downloads tile and summary field, runs a cleanup beat. | real, **1 smoke test** | keep | The token-serving view (expiry, count, IP) has no test. The Gutenberg import/convert commands (546 LOC of dotbooks content tooling) belong to book_product. Add tools: resend link, revoke or extend a token. 0 rows anywhere. |
| payments | Stripe and PayPal services, gateway registry and routing, `PaymentTransaction`, webhooks, `PaymentGatewayConfig`, health check. | real, 80 tests | keep; **absorbs advanced_payments and fraud_rules** | **Three dead models:** DB `PaymentGateway` (whose name clashes with the `gateway.PaymentGateway` ABC), `Payment` (0 refs), `PaymentMethod` (only ever deleted). **0 agent tools**: no way for Janus to list or enable gateways or set offline instructions. |
| advanced_payments | Two gateways: COD and a staff-only "test" gateway, plus `sync.py`, which projects its PluginConfig onto `payments.PaymentGatewayConfig`. That bridge exists only because the settings live in another app. | real, 237 LOC | **merge into payments** | COD has no `is_configured()` and `cod_enabled` defaults to True, so any store that never opened the panel offers cash on delivery. It overlaps payments' `manual` gateway, whose docstring already says "bank transfer, COD". |
| agentic_checkout | ACP 2026-04-17 server: `/.well-known/acp.json`, its own `feed.json`, checkout sessions backed by Cart, and a Stripe SPT money path behind a flag. Shopper tools `cart.*`/`checkout.*`. | real, 46 tests; off except dotbooks | keep opt-in | A second OpenAI-facing feed besides `openai_shopping` (whose docstring says OpenAI retired Instant Checkout in 03/2026); use `plugins/feed_mapping.py` only. Shopper cart tools sit beside agent_core's `cart.add_by_slug`/`cart.summary`. `requires google_shopping` only for mapping. |
| fraud_rules | ORDER_PLACED handler scores velocity, address mismatch, BIN, refund history and value, and writes `order.metadata['fraud_*']`. **Nothing displays the score**, and no tool reads it. | real logic, invisible output, 17 tests | **merge into payments** (risk is a payment concern) | `payment_bin` is never written, so the BIN denylist setting is inert. `auto_reject_at_score` has no reader. The hook is untagged. Show the score on the order page via a contribution and add a `orders.risk` tool. |
| shipping | Zones and rates, breakdown at priority 30 (honours promotions' `free_shipping`), CHECKOUT_SHIPPING_RATES, shipping JSON-LD, dashboard, 2 tools. | real, 19 tests | keep | Only dotbooks has a zone (rows 1/0/0/0). |
| smart_shipping | Two models never written (`CarrierEmission`, `OrderShipment`). There is no EasyPost or Shippo code. A `rate_list` block in `checkout_extra` renders **a second set of rate radio buttons** on the one-page checkout (where `rates` is in context), outside the form. | stub, active on all 4 stores | **delete** | eco_impact's docstring names it as the owner of shipping carbon, but it owns nothing. |
| eco_impact | Book production footprint on the PDP, "plant a tree" opt-in surcharge (breakdown priority 60, after every tender), impact page. `requires book_product`. | real, 13 tests; dotbooks only | **merge into book_product** (vertical), out of the default list | A "general" app hard-requiring a vertical (CLAUDE.md names this exact coupling). The surcharge is added after the gift-card tender (50), so a card never covers it, and any future handler above 60 that recomputes `total` from its parts silently drops it. |
| tax | Categories, regions and rates; breakdown at priority 20; dashboard; `tax.list_rates`/`set_rate`. | real, 13 tests | keep | 0 rows on every store: no live store charges tax. |
| markets | `Market` and `ProductMarketPrice`; middleware resolves a market per request; a context processor exposes `active_market`. **Nothing reads either:** no price hook (`price_for` has no caller), no template uses `active_market`, and `base_price_adjustment_pct` is dead. Its only effect is a `Content-Language` header. | stub on the money path | **merge into core channels** (or delete) | Middleware and context processor are hardcoded in `morph/settings.py:351`/`:425`, so they run when the app is disabled (CLAUDE.md landmine). It duplicates core `StoreChannel` + `ProductChannelListing` + `price_for`. A third country grouping beside ShippingZone and TaxRegion. |
| b2b | Price lists (dashboard page) applied **only** to the bulk CSV reorder; `Quote`/`QuoteLine` created by nothing in the UI and never converted; `NetTermsAgreement` read by nothing at checkout. Tools `b2b.list_quotes` (always empty) and `b2b.set_net_terms` (writes a row nothing honours). | mostly stub, 0 rows | **opt-in**; **quotes go to draft_orders** | Wire price lists to PRODUCT_CALCULATE_PRICE (display and charge, through `core/pricing.py`) or the page misleads merchants. Net terms need a payment-gateway leg (an "invoice" offline gateway) or should be removed. |

## Merges

**M1. Dissolve `marketing`: coupons into `promotions`, campaigns into `newsletter`, redirects deleted.**
- **Why:** One concept, coupons, has four homes today. The table is in marketing, the math is in promotions (`promotions/app.py:89-130`, which imports `marketing.models` without declaring the dependency), the CRUD is in the admin_dashboard shell (`admin_dashboard/views_split/marketing.py`, `forms/marketing.py`), and usage is counted in orders (`orders/services.py:496-541`). Disabling promotions silently stops every coupon from discounting while the coupon pages keep working.
- **What moves:** `Coupon` and `CouponUsage` move to promotions via `SeparateDatabaseAndState`, keeping the `marketing_coupon` table names, because `orders.Order.coupon` (`orders/models.py:37`) and orders' migration history point at `marketing.Coupon`. The coupon CRUD moves out of admin_dashboard into promotions. `EmailCampaign` moves to newsletter. `marketing.Redirect` is dropped (`seo/models.py:168` owns redirects). Rows are 0 on all stores, so no data needs copying; only the migration graph needs care.
- **Risk:** Money path (CART_CALCULATE_BREAKDOWN priority 10 stays the same, still before tax 20). `orders` gains a declared `requires: promotions`, or better, reads the coupon through a hook. Add coupon agent tools (`promotions.create_coupon`/`list_coupons`/`deactivate_coupon`) in the same change.

**M2. Fold `advanced_payments` into `payments`.**
- **Why:** COD and the staff-only test gateway are 60 lines of gateway code. `advanced_payments/sync.py` exists only to copy one app's settings into the other app's `PaymentGatewayConfig`, and COD overlaps the `manual` gateway.
- **What moves:** The two gateway classes plus the COD instructions field into payments' settings panel; `sync.py` is deleted. No models; the `cod`/`test` config rows stay as they are.
- **Risk:** Low. Keep the slug `cod` (orders' `OFFLINE_GATEWAYS`). Add `is_configured()` to COD and default it off.

**M3. Fold `fraud_rules` into `payments` (as `payments/risk.py`).**
- **Why:** The BIN signal can only come from the gateway, and today it is never written. The score is metadata no one sees.
- **What moves:** `services.py` and the handler (re-registered via `register_hook` so it is gated). No models.
- **Risk:** Low. It writes `order.metadata` on ORDER_PLACED at priority 85; keep the same priority.

**M4. Fold `returns_portal` into `orders`.**
- **Why:** orders already owns `ReturnRequest`, `ReturnService` and the RMA flow, and the storefront owns the return pages. The portal's two models are never written. What remains is one setting and one JSON-LD contribution, and seo reads that setting through a second reader (`seo/services/_helpers.py:288`).
- **What moves:** `return_window_days` and `seo_graph.py` move to orders, and orders **enforces** the window in `ReturnService.create_request`. Drop `ReturnResolution`/`ReturnFeedback` (0 rows).
- **Risk:** Low. Keep the published policy identical (head-parity profile).

**M5. Fold `post_checkout_upsell` into `post_purchase`, and delete `rich_post_purchase`.**
- **Why:** Both are "after the order" apps (receipt block plus follow-up journey). rich_post_purchase is an unbuilt extension of post_purchase.
- **What moves:** The template tag and block (no models). Drop `ChannelPreference` (0 rows).
- **Risk:** None to money.

**M6. Fold b2b quotes into `draft_orders`.**
- **Why:** `b2b.Quote` and `DraftOrder` are the same object (staff-priced lines, valid-until, convert to an order). Only the draft converts; nothing creates or converts a Quote.
- **What moves:** Drop `Quote`/`QuoteLine` (0 rows). `b2b.list_quotes` becomes `draft_orders.list`. If account linkage is wanted, b2b adds a OneToOne to `DraftOrder` holding the crm account (b2b keeps the dependency on crm, not draft_orders).
- **Risk:** Low.

**M7. Drop loyalty_points' RFM and tiers in favour of `customers.rfm`.**
- **Why:** `customers.recompute_rfm` is scheduled and fires CUSTOMER_SEGMENT_CHANGED. `loyalty.compute_rfm` and `loyalty.assign_tiers` are never scheduled, so `CustomerRFM`, `LoyaltyTier` and `CustomerTier` are empty duplicates.
- **What moves:** Nothing (0 rows). If tiers are wanted, compute them from `customers` segments.
- **Risk:** None.

**M8. Fold `markets` into core channels (`core/channels.py`: `StoreChannel`, `ProductChannelListing`, `price_for`), or delete it.**
- **Why:** Two parallel per-market price systems, and the markets one reaches neither the display price nor the charged price.
- **What moves:** dotbooks' single `Market` row becomes a StoreChannel if it is still wanted. Remove the middleware and context processor from `morph/settings.py`.
- **Risk:** Medium if anyone ever wires `ProductMarketPrice`; per CLAUDE.md, a price seam must fire on both display and charge.

**M9. `referrals` (and loyalty's dead `Referral`) to `affiliates`.**
- **Why:** A customer referral is an affiliate programme whose affiliates are customers and whose payout is store credit (`orders.StoreCredit`). affiliates already has links, attribution, conversions, reversal on refund, and a portal.
- **What moves:** Nothing (both referral implementations have 0 rows and no writers). Delete both. If wanted, add a "customer referral" program type to affiliates.
- **Risk:** Low.

**M10. `eco_impact` into the book vertical (`book_product`), and digital_products' Gutenberg commands into `book_product`.**
- **Why:** eco_impact `requires book_product` and returns nothing for non-books; it is installed only on dotbooks. The Gutenberg import/convert commands are dotbooks content tooling.
- **What moves:** `TreePledge` (0 rows) and the code. Remove both from the general default list.
- **Risk:** Low. The tree surcharge stays at priority 60.

**Delete outright:** `checkout_experience` (now; it is live-visible), `one_click`, `rich_post_purchase`, `smart_shipping`, `referrals`. Their tables are empty; ship a migration that drops them or leave the tables orphaned deliberately.

**Move out of the default-active list (opt-in):** `subscriptions` (0 rows; its footer link creates a soft 404 on every store), `b2b`, `agentic_checkout` (already `enabled_by_default=False`), `eco_impact` (vertical bundle), and `markets` if it is kept. Consider the same for `affiliates`.

**Result:** 27 apps become 15 (checkout_experience, one_click, rich_post_purchase, smart_shipping, referrals, marketing, advanced_payments, fraud_rules, returns_portal, post_checkout_upsell, markets and eco_impact all disappear as separate apps).

## Notable problems

1. **Live: a duplicate checkout form on every checkout.**
   - `checkout_experience/app.py:40-46` contributes `blocks/flow.html` to `checkout_extra`, which all three shop themes render (`themes/library/dot_books/templates/storefront/checkout.html:160`). There is no guard.
   - On dotbooks.store (checked 2026-10-12 with a real cart) it renders a "Contact / Shipping address / Payment / **Pay USD 0**" form below the real one.
   - Its submit redirects to `'/orders/' + n + '/confirmation/'` (`checkout_experience/static/checkout_experience/checkout.js:180`); the real route is `order/confirmation/<n>/` (`storefront/urls.py:102`).
   - `loader.html` (app.py:48-52) adds the script to `global_below_body` on every page of every store.
2. **post_purchase never sends anything.** `tasks.py:3` says "`process_due_steps` runs every 15 minutes", but no app calls `register_celery_beat` for it. The assembled `CELERY_BEAT_SCHEDULE` has no `post_purchase.*` entry. Review requests, NPS and the delivered follow-up queue forever.
3. **Hand-registered hooks bypass disable gating** (`hook_registry.register` without an owner; CLAUDE.md "deactivate() does NOT unwind ready()-wired hooks"). These keep firing after the app is switched off:
   - `post_purchase/apps.py:29-30`
   - `fraud_rules/apps.py:21`
   - `loyalty_points/services.py:92` (ORDER_PAID earns points)
   - `loyalty_points/apps.py:24`
4. **Coupon types the form offers but the engine ignores.**
   - The coupon form offers "Buy X get Y" (`admin_dashboard/forms/marketing.py:24`). `promotions/app.py:101-113` handles only percentage, fixed_amount and free_shipping, so such a coupon silently discounts $0.
   - `Coupon.applicable_products/categories/collections` and `exclude_sale_items` (`marketing/models.py:41-44`) are never evaluated.
   - Promotion action `gift` is recorded (`promotions/services.py:161`) but no free line is ever added to the order.
5. **Undeclared cross-app dependencies on the coupon path:**
   - `orders.Order.coupon` is an FK to `marketing.Coupon` (`orders/models.py:37`), and `orders/graphql/mutations.py:183` and `orders/services.py:469,496` import marketing and promotions. orders `requires = ['catalog','customers']`.
   - promotions imports `marketing.models` (`promotions/app.py:119`) with `requires = ['orders']`.
6. **marketing's own dashboard is dead code.** `marketing/dashboard.py` `coupons_list`/`campaigns_list` are shadowed by `admin_dashboard/urls.py:276`. The GraphQL extensions registered at `marketing/app.py:12-13` are empty files. `marketing/apps.py:13-14` writes `app_registry._classes` directly. The description advertises a "discount engine, abandoned-cart recovery" it does not have.
7. **Promotions dashboard.** The view has only `@staff_member_required` (`promotions/views.py:8`), no `require_capability`. It is read-only and tells merchants to use "the Django admin". `on_cart_total` (`promotions/app.py:163`) is dead: never registered, and its event is deprecated.
8. **Live soft 404: `/membership/` on every store.** The footer link (`subscriptions/templates/subscriptions/blocks/footer_link.html`, contributed at `subscriptions/app.py:73`) is unconditional. dotbooks serves `index, follow` with "No membership plans are available right now".
9. **markets runs while disabled and does nothing.**
   - `morph/settings.py:351` (middleware) and `:425` (context processor) are hardcoded. Contribute the processor via `register_context_processor` instead.
   - `markets/services.py:55 price_for` has no caller, and `active_market`/`market_currency` appear in no template.
10. **Returns.**
    - `return_window_days` is published to Google (`returns_portal/seo_graph.py`) but never enforced (`orders/refunds.py:213` accepts any age).
    - There is a duplicate reader at `seo/services/_helpers.py:288`.
    - `returns_portal/templates/returns_portal/blocks/cta.html:3` promises exchanges "ship within 48 hours", which nothing backs (CLAUDE.md "structured data / copy is a public claim").
11. **fraud_rules output goes nowhere.**
    - `services.py:149` reads `metadata['payment_bin']`, which nothing writes, so the `high_risk_bins` setting is inert.
    - `auto_reject_at_score` (`app.py:40`) has no reader.
    - The `fraud_score`/`fraud_bucket` metadata is shown in no dashboard and exposed by no tool.
12. **loyalty_points dead code and stale docs.**
    - `services_referrals.py`: `record_referral`/`referral_code_for` have no caller, so `qualify_on_order`, which runs on every ORDER_PLACED, never finds a referral.
    - `tasks.py:11,16` (`loyalty.assign_tiers`, `loyalty.compute_rfm`) are not scheduled.
    - `app.py:12-27` still says checkout redemption is "deferred", but it is wired (`views.apply_points`, `orders/services.py:587`).
13. **payments dead models.** `payments/models.py:9` (`PaymentGateway`, the DB model, 0 uses and a name clash with the `gateway.py` ABC), `:33` (`Payment`, 0 uses), `:89` (`PaymentMethod`, never written, yet `customers/services.py:179` imports it to delete rows).
14. **COD offered without configuration.** `advanced_payments/gateways/cod_gateway.py` has no `is_configured()` (the base returns True) and `cod_enabled` defaults to True (`advanced_payments/app.py:115`). This contradicts the CLAUDE.md rule that a payment method needs its prerequisites before it is offered. (Not visible on dotbooks' review step, which shows Stripe only.)
15. **smart_shipping's duplicate rate list.** `smart_shipping/blocks/rate_list.html` renders a second `name="shipping_rate"` radio group, outside the form, on `checkout_one_page.html` (which has `rates` in context). `lowest_carbon_id` is never supplied, so the badge never shows.
16. **b2b promises.** Price lists apply only in `services_bulk_order.py:157`, not to storefront or cart prices. `NetTermsAgreement` has no checkout consumer. `Quote` has no create UI and no conversion (`b2b/services.py:47` `create_quote` is called only by tests). `b2b.list_quotes` always returns nothing on a real store.
17. **Gift card surfaces survive a disable.** The storefront shell owns `/checkout/gift-card/apply|remove/` (`storefront/urls.py:34`, `views/checkout.py:318`). The themes hardcode the form (`dot_books/.../checkout.html:129-143`) without `{% plugin_enabled "gift_cards" %}`.
18. **Thin tests on money and download paths:**
    - promotions `evaluate()` (bogo, tiered, predicates; 353 LOC) has only staff-gate tests plus 4 mentions in `orders/tests/test_totals_breakdown.py`.
    - marketing: 0 tests.
    - digital_products' token download view: 1 smoke test.
    - returns_portal and checkout_experience: 0 discovered tests (their `tests/__init__.py` holds bare pytest functions the Django runner does not collect).
19. **Missing Janus tools for merchant actions** (CLAUDE.md, ADR 0039):
    - coupons: none at all
    - payments: none (gateways, offline instructions)
    - fraud: none
    - cart_abandonment: none
    - post_purchase: no NPS tool
    - newsletter: no campaign create or send
    - subscriptions: no plan create
    - draft_orders: no create
    - gift_cards: no void
    - promotions: no edit or deactivate, and only percent-off create
    - b2b: no price-list tools
    - digital_products: no resend or revoke
20. **Breakdown priority tie.** `subscriptions` member discount and `functions` both register CART_CALCULATE_BREAKDOWN at priority 40 (`subscriptions/app.py:40`, `functions/app.py:64-68`), so registration order decides which sees the other's discount. Give each a distinct priority.
