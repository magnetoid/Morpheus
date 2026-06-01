# Morpheus backlog — autonomous run (2026-06-01)

Driven via ralph-loop in autonomous mode. **Review at the end**, not per-step.

## Standing rules (every iteration)

- Follow `CLAUDE.md` house rules: surgical changes, simplicity first, docs
  ship with code (Living-Document table), migration before merge for any
  new model, permission-boundary tests for every new staff/customer view.
- **Commit locally at each logical boundary. NEVER `git push`.** Pushing
  triggers a Coolify deploy and rapid pushes thrash it (ERR_CONNECTION_RESET).
  Shipping is the user's explicit "ship" — leave deploy to them.
- Verify before claiming done: `python -m py_compile` for Python; Django
  template `{% %}` tag-balance for templates; re-fetch the live URL for
  storefront-visible fixes where possible.
- Branch is `main`. Make commits on a feature branch if the change is large;
  small fixes can commit to main locally (still no push).
- One concern per commit. Conventional-commit messages.

## Completion

Emit `<promise>MORPH BACKLOG COMPLETE</promise>` only when every item below
is done + verified, with a final honest report (what shipped, what's left,
what needs the user's decision).

---

## Phase 1 — three quick fixes (batch into one logical group)

### 1. Storefront raw-HTML / SEO leak  ✅ root-caused
`short_description` became a rich-text (HTML) field, but plain-text consumers
render it escaped → visitors + Google see literal `&lt;p&gt;`.
Evidence: `https://dotbooks.store/products/utopia-dotbooks-public-domain-edition/`
- meta description / og / twitter (lines ~9/13/23) = `&lt;p&gt;A premium…`
- JSON-LD `description` (line ~25) = `<p>A premium…`
- `pdp-variant__desc` (product_detail.html:99) = `&lt;p&gt;…&lt;/p&gt;`

**Fix:** strip HTML wherever short_description is used as plain text:
- `themes/library/dot_books/templates/storefront/product_detail.html:99`
  → `{{ v.shortDescription|striptags|truncatewords:14 }}`
- `:84` data-variant-desc → `|striptags|escape` (or strip in JS)
- SEO meta builder + JSON-LD builder (locate in `plugins/installed/seo/`)
  → `striptags`/`strip_tags` on the description before output.
**Accept:** curl the PDP — no `&lt;p&gt;` in meta, JSON-LD, or variant desc;
long description (`|safe`) still renders HTML.

### 2. Short & long description not showing in product edit form
`product_form.html` has TipTap RTE editors (short/long) backed by hidden
textareas seeded from `form.short_description.value` / `form.description.value`.
**Diagnose:** is the editor failing to mount (JS), or is the stored value
double-escaped entities? Likely tied to #1 (value is HTML/escaped).
**Accept:** opening an existing product shows its current short + long
description content inside both editors.

### 3. Category picker → multi-select dropdown
Today: single `<select>` "Primary category" + an `additional_categories`
checkbox grid (CSV hidden input). Keep PRIMARY canonical (SEO/breadcrumbs);
convert the additional-categories grid into a **multi-select dropdown** that
writes the same `additional_categories` CSV.
**Accept:** can pick several categories from a dropdown; saves + reloads
correctly; primary still separate.

---

## Phase 2 — feature builds (audit first, short spec, then build)

For each: (a) audit existing code + report works/breaks, (b) write a one-page
spec under `docs/plans/`, (c) build incrementally with migrations + boundary
tests, (d) verify.

### 4. Unified Payments settings page + test gateway
Today payment config is scattered across plugins/apps. Build one
`Settings → Payments` page listing every payment gateway/plugin with its
enable toggle + config, and add a **test/manual gateway** option for trying
checkout without a real processor. Audit existing payment plugins first
(`grep` for gateway registration / checkout providers).

### 5. Loyalty points app (continue)
Audit the existing loyalty plugin state, then continue the next increment.
Keep it a plugin (CLAUDE.md compass). Boundary tests for any staff view.

### 6. Extensive affiliate app + audit
"Check fully if everything works" → audit the existing affiliate app first,
report. Then build it out: many options, and **embeddable shop widgets**
(embed parts of the shop on external sites). Plugin, not core.

---

## Progress log
- [x] Phase 1.1 storefront HTML leak — commit 4bbf102. strip_html helper in
  seo._helpers applied at resolve_meta / _structured_data_for / product_jsonld /
  PDP variant serializer + pdp_seo_description. Lede stays |safe.
- [x] Phase 1.2 descriptions blank in product form — commit 82c9dd6. ROOT CAUSE:
  dashboard enforcing CSP script-src lacked esm.sh (TipTap CDN), so editors never
  mounted + hidden textareas hid the content. Added esm.sh to dashboard script-src.
- [ ] Phase 1.3 category multi-select dropdown — in progress.
- New small dashboard bugs queued (treat as quick fixes):
  - Dashboard menu collapse/expand needs TWO clicks, should be ONE.
  - Affiliate left menu has non-clickable sub-titles — remove (off-pattern).
- Verify all storefront/CSP fixes against live URL AFTER user ships (not pushed yet).

## Progress log (continued)
- [x] Nav: one-click section toggle + sticky settings nav — commit e2b556e.
- [x] catalog dedupe_numbered_slugs mgmt command (dry-run) — commit 789ec47.
  BLOCKED on user: destructive on prod. Needs deploy to run + user to review
  dry-run output before --delete. DO NOT auto-delete prod products.
- [x] Affiliate sidebar: removed non-clickable nav-subheader spans — commit 70f904e.

## Audit findings (from 3 background Explore agents, 2026-06-01)

### Payments (unify + test gateway)
- Plugin `plugins/installed/payments/` already has: `gateway.py` PaymentGateway
  ABC + GatewayRegistry (`gateway_registry`, .all()/.get()/.default()), and TWO
  registered gateways — `ManualGateway` (slug 'manual', gateways/manual_gateway.py)
  and `StripeGateway` (gateways/stripe_gateway.py). Registered in plugin.py ready().
- Settings→Payments today only renders a Stripe panel (plugin.py contribute_settings_panel).
- Checkout is HARDCODED to Stripe (services/stripe.py); does NOT use the registry.
- PLAN: build a settings_payments() view + template iterating gateway_registry.all(),
  each with enable toggle + per-gateway config (store in a PaymentGatewayConfig model or
  PluginConfig). The "test gateway" = ManualGateway, just needs UI exposure. Optionally
  wire checkout to gateway_registry.get(selected_slug).

### Affiliate (audit = WORKS; gaps for "extensive + embeddable")
- `plugins/installed/affiliates/` is complete + registered (settings.py:63): 6 models
  (AffiliateProgram/Affiliate/AffiliateLink/AffiliateClick/AffiliateConversion/AffiliatePayout),
  storefront + admin views, services, graphql, migrations, tests. No TODOs/breakage found.
- GAPS for "extensive": tiers/levels, campaign bonuses, perf-based auto-approve, per-product
  rates, automated payout schedule. For "embeddable shop widgets": NONE today — need a new
  AffiliateWidget model, CORS JSON API (e.g. /api/affiliates/widget/products?ref=CODE), an
  embeddable iframe/script bundle, per-affiliate branding, external click beacon. LARGE; needs
  a design decision from user before building.

### Dashboard UX/IA standardization (top 5, highest impact first)
1. Replace ad-hoc `w-full text-sm`+`px-4 py-2` tables with `.morph-table` (categories.html,
   errors_list.html, errors_detail.html).
2. Standardize page header = breadcrumb + 2-col flex (h1+subtitle left, actions right) on all
   list pages; deviants: home.html, ai_insights.html, returns_list.html, errors_list.html,
   analytics.html (missing breadcrumb / off-pattern header).
3. Move Tracking + Errors OUT of settings nav into a main-nav "Admin tools" group (they're ops
   tools, not config) — fixes the config-vs-ops mental model.
4. Add `.btn-secondary` (outline) variant; retire inline border-styled buttons (products.html
   "Improve with AI").
5. Replace hand-coded empty states with `_empty_state.html` (categories.html, errors_list.html).
- Also: consistent `space-y-4`; `.form-help` class; don't use `.pill` for tabs (customers.html).

## Payments unification (item #4) — v1 SHIPPED (working tree, not committed)
Built the unified **Settings → Payments** page. One card per gateway in
`gateway_registry.all()` with: label, capability badges (refunds/webhooks),
enable toggle, and per-gateway config (Stripe: secret/publishable/webhook keys +
capture strategy; Manual: customer-facing instructions textarea). Manual / offline
IS the test gateway — enable it to run checkout end-to-end without a processor.

Decisions taken:
- **Storage = new model** `payments.PaymentGatewayConfig` (slug unique, enabled bool,
  config JSON) + migration `0003_paymentgatewayconfig`. `is_enabled(slug)` helper with
  `DEFAULT_ENABLED = {'stripe','manual'}` so a fresh install never has zero methods.
- **Surface = custom view** `admin_dashboard.views_split.settings.settings_payments`,
  dispatched from `settings_category('payments')` (same pattern as `ai`/`caching`).
  Template `settings_payments.html`. No new URL (reuses the staff-gated
  `settings/<category>/` route); boundary triplet still added for the new view.
- **Registry helper** `gateway_registry.enabled_gateways()` filters by `is_enabled`
  (read-only, low-risk).

DONE — checkout gateway selection (was deferred; now wired):
- `payments/services/routing.py` is the single routing entry point.
  `complete_order` (and the standalone `createPaymentIntent`) call
  `create_payment_intent_for(order, selected_slug)` instead of hardcoding
  Stripe. The slug is validated against `enabled_gateways()`; empty / unknown /
  disabled → `default()` (stripe), so the live Stripe path is unchanged when no
  method is picked. The resolved slug is recorded on `Order.payment_gateway`
  (migration `orders/0011`); refunds route back through it.
- Storefront picker: `checkout_one_page.html` renders one radio per
  `picker_gateways()` entry (default-selects stripe); the chosen slug rides the
  `completeOrder` mutation as `paymentGateway`.
- Contract tests: `payments/tests/test_routing.py` (real ABC + registry, only the
  Stripe SDK boundary mocked) — stripe shape preserved, manual/cod/test offline
  success, disabled/unknown → stripe fallback, fail-soft on gateway error.

## Remaining work + blockers (for final report)
- UX standardization: do the 5 above (unambiguous, safe). IN PROGRESS.
- Payments checkout wiring: DONE per the section above (per-order gateway
  selection + honoring `enabled_gateways()` in the payment-intent flow, routed
  through `payments/services/routing.py` with contract tests).
- Loyalty app: NOT yet assessed — find plugins/installed/loyalty*, report state, continue.
- Extensive affiliate + embeddable widgets: LARGE, needs user design decision on widget approach.
- Prod product dedup: BLOCKED — needs user to review dry-run + confirm before --delete.

## UX standardization progress (item #8)
- [x] Tables → .morph-table: categories (8787b70), errors_list (be9c01a), errors_detail (75e2bea).
- [x] .btn-secondary accent-outline variant + retire inline button styles (b54e747).
- [x] Empty states → _empty_state.html: errors_list (be9c01a), categories (eacb67a).
- [ ] #2 page-header/breadcrumb pass (home, ai_insights, returns_list, errors_list, analytics
  lack breadcrumbs / off-pattern headers) — multi-file, partly cosmetic; verify each view
  actually provides breadcrumb_trail before adding the include.
- [ ] #3 move Tracking + Errors out of settings nav into main nav — DEFERRED: base.html:734,779
  show this placement was a DELIBERATE prior decision. Needs user confirm before reversing.

## Notes / open scope calls (resolve with sensible defaults, flag in report)
- Embeddable widgets: likely an iframe/JS-snippet endpoint serving product
  cards/grids with an affiliate ref param. Confirm CORS + theming approach.
- "Lots of options" for affiliate: commission tiers, cookie window, payout
  tracking, per-link analytics — scope to a reasonable v1, list the rest.

## Loyalty redemption (v1 shipped + remaining wiring)

Shipped (2026-06-01) in `plugins/installed/loyalty_points/`:
- Config: `redemption_rate` (points per 1.00, default 100) + `max_redeem_fraction`
  via the plugin settings panel (`plugin.py` → `contribute_settings_panel`,
  category `marketing`).
- `services_redeem.py`: `points_to_amount` / `amount_to_points` (round down on
  credit, up on cost — never over-credit), `max_redeemable(customer, order_total)`,
  `redeem_points(customer, points, order=…)` (negative `spend_order` ledger row,
  returns the discount Money), `reverse_redemption(...)` for cancels/refunds.
- Breakdown hook: `LoyaltyPointsPlugin.on_cart_breakdown` answers
  `CART_CALCULATE_BREAKDOWN` at priority 15 — runs AFTER promotions/coupons/gift
  cards (priority 10) so points cap against the already-discounted total, and
  BEFORE tax (20) / shipping (30). Reads `cart.metadata['loyalty_points_redeem']`,
  caps via `max_redeemable`, folds the value into `discount`+`total`, stamps
  `meta['loyalty_points']`.
- Customer surface: `/account/points/` (balance + what it's worth + ledger),
  linked from account home. Boundary triplet + service + math tests in
  `tests/test_redeem.py`. No model change → no migration.

REMAINING checkout wiring (deliberately deferred — NOT hacked):
1. **Cart endpoints** `/checkout/points/apply/` + `/checkout/points/remove/`
   (storefront plugin) that write an int to `cart.metadata['loyalty_points_redeem']`,
   bounded by `services_redeem.max_redeemable(customer, breakdown['total'])`, plus
   a checkout-page affordance ("Use N points → −$X"). Until this exists the
   breakdown hook is a NO-OP on live carts (nothing writes the metadata key), so
   shipping the hook now is safe.
2. **Order-time ledger debit.** In `orders/services.py:OrderService.create_from_cart`,
   mirror the existing gift-card block: when `breakdown['meta']['loyalty_points']` is
   present, call `services_redeem.redeem_points(cart.customer, points, order=order)`
   inside the same atomic txn, fail-soft + audit on error (same pattern as
   `gift_card_redeem_failed`). This is the ONLY edit that touches the orders plugin.
3. **Refund/cancel reversal.** Subscribe `reverse_redemption` to ORDER_CANCELLED /
   refund events (read `order` → its `loyalty_points` spend rows by `order_number`)
   so a shopper isn't out the points on a reversed order.
4. Idempotency: step 2 must guard against double-debit on checkout retry — check for
   an existing `spend_order` row on `(customer, order_number)` before debiting.
