# Boundary & duplication debt — repayment plan (2026-07)

Source: full-codebase audit (2026-07-10), three sweeps — plugin boundaries /
disable-safety, duplication / dead code, CLAUDE.md convention drift. The
quick wins shipped in the same batch as this doc (lint gates, secret
masking, ajax error paths, Money precision, `is_staff`/`money_str` dedup,
orphan-template removal, stale test import). What remains below is the
work that touches live-revenue paths or needs a design decision — do each
as its own PR with tests, not as a sweep.

## 1. bookvault shell leak — the named ADR-0023 open item

`admin_dashboard/views_split/products.py:96,404` hard-imports
`bookvault.services` + models to render the product-list status column and
the fulfilment card; `products.html:45` posts to `{% url 'bookvault:bulk_link' %}`
and `product_form.html:761` hard-codes the card. Self-hides on
`is_authenticated()` but survives disable-while-configured.

Fix (as CLAUDE.md prescribes): move the card to
`PRODUCT_FORM_CARDS`/`PRODUCT_FORM_SAVED`, add a `PRODUCT_LIST_COLUMNS`
filter for the list column (new hook, mirrors `PRODUCT_FORM_CARDS`), wrap
the remaining template references in `{% plugin_enabled "bookvault" %}`.
Verify with a disable-guard test alongside `test_disable_guards.py`.

## 2. Other shared-shell leaks (same class, same fix pattern)

Optional plugins rendered by direct import instead of contribution
(~74 import lines; the try/except ImportError guards protect *absence*,
not *disable*):

- **product_videos** — `products.py:386,723,762,805`, `storefront/views/catalog.py:453`
  → `PRODUCT_FORM_CARDS` + a storefront block.
- **metafields** — `products.py:259-263,288`, `storefront/views/catalog.py`
  (5 sites), `vendor.py:22` → form card + contributed block.
- **cloudflare** — `settings.py:435-436,458-459,572,584,602`
  → `contribute_settings_panel`.
- **seo** — `products.py:195,305`, `settings.py:416,624` → form card + panel.
- **ai_assistant / ai_content / analytics dashboards** —
  `ai_insights.py:19`, `_shared.py:344,352`, `settings.py:184`,
  `analytics.py:247` → `DASHBOARD_HOME_PANELS` / `DASHBOARD_KPIS`
  contributions (the mechanism the home page already uses).
- **storefront account sub-pages** (documented known debt) —
  `account.py` queries gift_cards/store-credit/returns models directly;
  `content.py` queries crm/cms/consent → each plugin contributes its own
  account page (own URL + template), summary already fixed via
  `ACCOUNT_SUMMARY_FIELDS`.
- **storefront checkout/search — DONE (2026-07-10)**: shipping rates,
  gateway picker, hybrid search and PDP similars now flow through
  `CHECKOUT_SHIPPING_RATES` / `CHECKOUT_GATEWAYS` / `SEARCH_RANKED_IDS` /
  `SIMILAR_PRODUCTS` (tests: storefront/tests/test_checkout_hooks.py).
  The rewire exposed that checkout's rates import (`compute_rates`) never
  existed — configured shipping rates had silently never shown at checkout.
- **storefront personalisation — DONE (2026-07-10)**: the four direct
  `rank_for_visitor` imports (home featured, PLP, category, collection)
  now fire `PRODUCT_LIST_REORDER` — the filter personalisation was already
  subscribed to; the shell just wasn't using it.
- **Still open in catalog.py**: book_product (9 sites), metafields (5),
  product_videos (1) — the book-vertical data integrations; need a
  facet/specs contribution design before migrating.

## 3. customers ↔ orders cycle + GDPR fan-in — DONE (2026-07-10)

Cart-merge-on-login moved to an orders-owned CUSTOMER_LOGIN subscriber;
the GDPR export/erasure now assemble via CUSTOMER_DATA_EXPORT /
CUSTOMER_ANONYMISE (each of orders/catalog/consent/wishlist/loyalty_points/
affiliates/payments contributes its own gdpr.py slice). customers imports
no sibling plugin. Guarded by customers/tests/test_gdpr_hooks.py.

### (was) customers ↔ orders cycle + CDP fan-in

`customers/signals.py:19-20` imports orders (cart merge on login) while
orders `requires` customers — a requires-cycle in reverse. And
`customers/services.py` (`update_cdp_metrics`/`gather_customer_data`)
imports catalog/consent/wishlist/loyalty_points/affiliates directly.

Fix: cart-merge moves to an orders-owned login subscriber; CDP aggregation
becomes a `CUSTOMER_METRICS` filter each plugin feeds (the ADR-0031
`BRAIN_SIGNALS` pattern) so inactive owners drop out automatically.

## 4. Channel-plugin feed mapper — DONE (2026-07-10)

Consolidated into `plugins/feed_mapping.py` (FeedMapper + Google/Meta
subclasses); the six files are now thin adapters. Behaviour verified
byte-for-byte against pre-consolidation goldens
(`google_shopping/tests/test_feed_mapping_shared.py`).

### (was) 6 near-identical ~200-line files

`{google_shopping,meta,pinterest,snapchat,tiktok,microsoft}_commerce/services/mapping.py`
are ~96% identical (diffs: docstring, `_NS`, logger name). Same for the
CAPI leaf helpers `_money`/`_line_items` (5 copies).

Fix: one shared feed-field resolver parameterised by namespace, living in
shared plugin infrastructure (e.g. `plugins/feed_mapping.py`, beside
`plugins/context_processors.py` — NOT in one channel plugin, and it's not
core-worthy). Channels keep only their overrides. High blast radius (live
merchant feeds, Redis-cached — bust the cache on deploy per the
google_shopping incident): land with per-channel golden-file tests
snapshotting current feed output *before* the merge, then diff after.

## 5. Smaller consolidations

- `_trail(*items)` breadcrumb builder: 8 plugin copies + 1 variant. Home:
  `morpheus` plugin SDK (where `DashboardPage` lives) so plugins don't
  import admin_dashboard. Signature: `dashboard_trail(root_label, root_url, *items)`.
- `zip(names, prices)` row-parsing style in dashboards: leave; noted only.

## 6. Decisions needed (not code yet)

- **demo_data**: fully built (manifest, dashboard page, URLs, tests) but
  absent from `MORPHEUS_DEFAULT_PLUGINS`, so every line of it is dead.
  Register it (it ships a "Demo data" app to prod) or move it out of
  `plugins/installed/` to a dev-fixtures location. Owner call.
- **core/assistant/tools/*** → `contribute_agent_tools()` migration
  continues (baseline is ratchet-only, 11 entries left; `bf5e9c3f` shows
  the pattern — and remember its lesson: grep *all* test imports when
  moving a tool).
