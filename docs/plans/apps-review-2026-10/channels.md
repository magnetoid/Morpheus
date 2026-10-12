# Channels, ads, analytics, automation, integrations, suppliers: app review (25 apps)

Cluster totals: 26.2k LOC, 434 tests, 38 agent tools, 41 models. On the four live stores (dotbooks/supernatural/montenegro/irving) real data exists only in **analytics** (593k/162k/118k/1.3k rows), **tracking** (3.4k/1.7k/108/437), **notifications_center** (6.1k/16/3/0) and **feature_adoption** (~100 per store). The channel apps' rows are their own feed-build logs written by beat (4 a day for about 94 days ≈ 376 on dotbooks). Nothing in that data shows a connected channel. The supplier, webhook, workflow, function, cloudflare and importer tables are empty on every store.

## Per-app table

| App | What it really does today | Real / stub | Verdict | Key improvements |
|---|---|---|---|---|
| channels | Aggregator with two pages: Overview (status rows from `CHANNELS_OVERVIEW` plus cached ad KPIs from `CHANNELS_METRICS`) and ROAS (platform-claimed vs last-touch revenue). Two beats (overview every 30 min, metrics daily). No models | Real | **Keep as the merge target** (absorbs 9 channel apps); move ROAS page to analytics | Hardcoded channel/utm lists (8 names, openai missing); undeclared `analytics` import |
| google_shopping | RSS feed `/feeds/google-merchant.xml` (shared `FeedMapper`), coverage report, Content API push (6 h beat, no-op until OAuth), Google Ads report/status/budget/create, remarketing tag. 5 read tools + rebuild | Feed real. API layer pinned to Ads API v17 and Content API v2.1, likely dead against live Google | **Merge into channels** (google adapter) | Dead `currency`/`free_shipping_over` settings; "Dot Books" default feed title; book_product read without `is_active`; campaign write tools |
| meta_commerce | Feed `/feeds/meta-catalog.xml`, Catalog API push, Pixel, CAPI (Purchase/AddToCart/InitiateCheckout, sent inline), Marketing API (report/status/create), Custom Audience upload | Real | **Merge into channels** | CAPI not consent-gated and blocking; `sync_audience` uploads every user incl. staff under a read scope; dead `country` |
| microsoft_commerce | Same RSS feed (identical code to pinterest/snap/tiktok), UET tag, Bing Ads SOAP campaigns + reporting | Real | **Merge into channels** | Dead `country`; feed cache 1 h vs 6 h rebuild |
| pinterest_commerce | Same feed, tag, CAPI, Ads v5 list/status/create/report | Real, thin | **Merge into channels** | Same as above; CAPI consent |
| snapchat_commerce | Same feed, pixel, CAPI, Ads list/status/create/report | Real, thin | **Merge into channels** | Same |
| tiktok_commerce | Same feed, pixel, Events API, Ads list/status/create/report | Real, thin | **Merge into channels** | Same |
| openai_shopping | JSONL feed for ChatGPT/Perplexity in OpenAI's spec, optional 6 h push to an allow-listed endpoint, overview row | Real | **Merge into channels** (it is a feed channel) | Return policy and availability are published from defaults; push URL gets no egress check; no tool |
| amazon_ads | Amazon Ads API only: Sponsored Products list/status/budget/create + async report. No feed or pixel; declares `requires=['catalog']` but never uses it | Real, thin, 0 rows | **Merge into channels** (ads-only adapter) | Campaign write tools |
| reddit_ads | Reddit Ads list/status/create/report, pixel, CAPI, plus a hardcoded list of **book** subreddits exposed as a Janus tool | Real, thin, 0 rows | **Merge into channels**; drop `book_communities` | Bookshop vocabulary in a default app |
| tracking | GA4 Measurement Protocol (queued on Celery, crawler filter), GTM container + export, Consent Mode v2 defaults, event log, test bench, Google Ads purchase-conversion tag, **its own cookie banner** | Real, used | **Keep** | Remove its banner (the consent app owns that); gate the Ads conversion tag on consent; prune `GA4EventLog`; 0 tools; 6 tests for 1.7k LOC |
| analytics | First-party store: sessions, events, daily rollups, funnels, cohorts, realtime, anomaly alerts, multi-touch attribution with `AdSpendSnapshot`. 7 read tools | Real, most used | **Keep**; absorb feature_adoption and the channels ROAS page | Ad spend overstated ×30 (see P5); undeclared imports of orders/consent/notifications_center; no attribution/cohort tool |
| experiments | A/B models, `{% variant %}` tag, Wald significance, a seeded draft "checkout_flow" | **Dead**: tag used nowhere, cookie middleware installed nowhere, no UI or tool; the 1 row per store is the seed | **Delete** | Remove `{% load experiments %}` (supernatural cart.html:3) and the dynamics consumer in the same change |
| feature_adoption | Counts staff dashboard hits and agent-tool calls per app (cache, flushed hourly to `FeatureUsageDay`); health-score card on the Analytics landing | Real, small | **Merge into analytics** | Show "last used" per app in the Apps catalogue; that is the evidence for pruning apps |
| observability | One page listing `core.audit.AuditEvent`; a retired `ErrorEvent` table (1,360 frozen rows on dotbooks); an uncalled `record_error` shim | Thin | **Delete**: audit-log page moves to core | Audit log is a safety surface and should not be something you can disable; drop the dead table |
| notifications_center | Staff inbox (one `Notification` per staff user), bell in the dashboard shell, low-stock/out-of-stock/agent-failed subscribers | Real, used | **Keep** (invert coupling) | 4 apps + `plugins/context_processors.py` import it directly; no dedupe, no prune; no Janus tool |
| webhooks_ui | CRUD for `core.WebhookEndpoint`, delivery log, retry/replay; subscribes to 12 events and enqueues deliveries, while core already delivers the same events | Real, 0 rows | **Merge into core webhooks** (one dispatcher) | Double delivery (P4); 2 tests; no tools |
| functions | AST-restricted "python_safe" sandbox run on `PRODUCT_CALCULATE_PRICE` + `CART_CALCULATE_BREAKDOWN`. GraphQL test-run only; no way to create a Function outside Django admin | Effectively dead, 0 rows | **Delete** | A timed-out thread can't be killed, and it sits on the money path |
| workflows | Event → JSON condition → 5 actions (notify staff, order note, tag customer, webhook POST, run agent). Dashboard CRUD + `workflows.run` | Real, 0 rows, engine untested | **Merge into agent_core automations** (event triggers) | Runs inline in the request that fired the event, including an LLM run; SSRF on webhook POST |
| importers | Shopify (REST 2024-01) and CSV *products* import/export in the dashboard; WooCommerce via CLI only; Magento/BigCommerce are choices with no adapter | Real, partial (already off on dotbooks) | **Opt-in** | Run imports on Celery (today they run inside the request); stop claiming Magento/BigCommerce; tools |
| dsers | CSV bridge: link product to AliExpress URL, export an order sheet for DSers, import a tracking CSV → `Order.ship()` | Real, 0 rows | **Merge into dropshipping** | No tools |
| zendrop | Zendrop MCP client: place orders, read status/tracking; link table | Real, 0 rows | **Merge into dropshipping** | No tools |
| aliexpress | AliExpress DS API: import a product as a priced draft, auto-forward on `ORDER_PAID` (one AE order per seller), optional auto-pay, 30 min tracking sweep | Real, 0 rows | **Merge into dropshipping** | Double-forward risk (see Merges) |
| cjdropshipping | CJ API: import, auto-forward, pay, HMAC-verified webhooks, 20 min sweep | Real, 0 rows | **Merge into dropshipping** | Same |
| cloudflare | Zones/DNS/purge/analytics/firewall pages; auto-purge on product/category/SEO writes; GraphQL | Real, unconfigured on all 4 stores | **Opt-in** | Purge runs inside the product-save request, before commit; no `purge` tool |

## Merges

**M1. Fold google_shopping, meta_commerce, microsoft_commerce, pinterest_commerce, snapchat_commerce, tiktok_commerce, openai_shopping, amazon_ads and reddit_ads into `channels` (9 → 1).**
- **Shape:** `channels/adapters/<name>.py`, each implementing a small protocol: a feed mapper subclass and feed path, a pixel template, a conversions sender, an ads client (report/list/set_status/create) and OAuth. The shell is shared: one feed view, cache and rebuild task per channel; one `ChannelSyncLog(channel, kind, status, …)`; one settings panel with a section and an on/off switch per channel; one dashboard and one ads template rendered per channel.
- **Why (measured):** for the six feed channels, average pairwise similarity after normalising names is feed.py 0.91, coverage.py 0.90, settings.py 0.78, oauth.py 0.80, models.py 0.77 (max 0.93), urls 0.96, dashboard.html max 0.95, ads.html max 0.97. Five `build_feed`, five `_build_coverage_report` and four `rebuild_feed` are identical after normalising channel names. 32 functions repeat across apps (~800 redundant lines). The 30 agent tools are mostly the same 4 concepts, repeated (`*.feed_coverage` ×6, `*.feed_url` ×5, `*.ads_report` ×7, `*.campaigns` ×3), so one `channels.*` family with a `channel` argument would need about 8. Navigation today is 17 tabs in the Channels section plus 9 settings panels. I expect about 11.1k LOC → 5–6k.
- **What moves:**
  - Each app's PluginConfig (OAuth refresh tokens, pixel/ad-account ids), via a data migration to `<channel>.<key>`.
  - 8 sync-log tables holding 3,363 rows in all (google 11, meta 8, microsoft 835, pinterest 836, snapchat 837, tiktok 836, amazon 0, reddit 0, summed over stores). These are beat noise: drop them, or keep 30 days.
  - Feed URLs and the `google.*`/`meta.*` metafield namespaces stay exactly as they are.
- **Gains:** one consent-gated, Celery-queued conversions dispatcher for the five CAPIs (fixes P1 and P11). A channel that isn't connected runs no beats, pixels or hooks.
- **Risk: medium.**
  - A secret missed in the config migration silently disconnects a channel.
  - Tool names are stable API, so keep aliases for one release and add a MIGRATING.md entry.
  - 165 tests need re-homing.
  - Do it in two steps: (a) a channel kit at the `plugins/` root, like `feed_mapping.py`, called by the existing apps; (b) collapse the apps.

**M2. Fold dsers, zendrop, aliexpress and cjdropshipping into one opt-in `dropshipping` app (4 → 1), promoting `plugins/dropshipping/` from library to app.**
- **Shape:** one `SupplierProduct(variant unique, supplier, supplier_product_id, supplier_variant_id, url, cost, currency, stock)` replaces SupplierLink, ZendropLink, AELink and CJLink. One `SupplierOrder(order, supplier, status, supplier_order_ids, tracking, carrier, …)` replaces OrderSync, ZendropOrder, AEOrder and CJOrder. Adapters: dsers (CSV), zendrop (MCP), aliexpress (DS API), cj (API + webhooks).
- **Why:**
  - The code itself is not very duplicated (similarity 0.25–0.6, 11 shared functions, ~74 lines), because the supplier APIs differ. The model layer, though, is four parallel tables for one concept, which CLAUDE.md's "one concept = one model owner" rule forbids.
  - Each app adds its own product-form card, dashboard page and settings panel. Irving's product editor shows three supplier cards.
  - A variant linked in both AliExpress and CJ is forwarded to **both** on `ORDER_PAID`, which means two paid supplier orders. Nothing prevents this today; a unique variant makes it impossible.
- **What moves:** all 8 tables have 0 rows on every store, so no data migration. Only PluginConfig moves: dsers on supernatural, zendrop on supernatural and irving, aliexpress and cj on irving.
- **Risk: low.** Add the supplier tools once (send/pay order, import product, link variant, import tracking) instead of four times.

**M3. Fold workflows into agent_core automations.** An automation gets `trigger = cron | event`, plus the workflow JSON condition. Its actions are the four fixed actions or "ask Linda".
- **Why:** both apps are "when X, do Y". Automations already run on Celery and already carry the "an automation can never consent" rule. Workflows run inline inside the request that fired the event: an LLM `run_agent` and a 10 s POST on `order.paid`.
- **What moves:** 0 rows.
- **Risk: low.** Keep the `workflows.run` name as an alias.

**M4. Fold feature_adoption, and the channels ROAS page, into analytics.**
- **feature_adoption:** its card already sits on the Analytics landing. `FeatureUsageDay` (~100 rows per store) moves with `SeparateDatabaseAndState`, keeping the table name, so zero SQL.
- **Two attribution pages, two spend pipes:**
  - channels ROAS reads `CHANNELS_METRICS`, which covers 8 channels.
  - analytics Attribution reads `ANALYTICS_AD_SPEND`, which only Google and Meta feed.
  - Google and Meta each make the same live 30-day report call twice a day to serve both (google_shopping/app.py:55 and :102; meta_commerce/app.py:54 and :102).
- **Fix:** keep one page in analytics that reads the channels' cached metrics. Delete `ANALYTICS_AD_SPEND` and the `_ad_spend` handlers.
- **Risk: low.**

**M5. Fold webhooks_ui into core webhooks (one dispatcher).**
- **Why:** core already owns `WebhookEndpoint` (core/models.py:242) and already delivers every event to it (core/hooks.py:114 → :296-312 → `core.tasks.dispatch_webhook`).
- **Change:** move `WebhookDelivery` (0 rows) and retry/replay into core's dispatcher. Delete webhooks_ui's fan-out. The CRUD page becomes a core developer page. This fixes P4. The inverse (move dispatch out of core into the app) is also fine; what matters is a single dispatcher.
- **Risk: low.**

**M6. Fold observability into core/audit.**
- **Change:** move the audit-log page into core. Drop `observability.ErrorEvent` (1,360 stale rows on dotbooks; `core.errors.ErrorEvent` replaced it under ADR 0025) and the uncalled `services.record_error`.
- **Risk: low.**

**Delete outright:**
- **experiments:** dead (P6). Its only rows are the seed.
- **functions:** 0 rows, no way to author a function, and an unkillable sandbox thread on the price path. Janus plus pricing rules cover merchant logic.

**Move out of the default list (opt-in via `MORPHEUS_EXTRA_APPS`):**
- **cloudflare:** 0 rows on every store, yet its hooks run on every product save.
- **importers:** a one-off migration tool, already off on dotbooks.
- **dropshipping:** the merged supplier app stays opt-in.
- **Inside channels:** every adapter is off until it is connected.

**Keep:**
- **tracking:** but drop its banner and fix the consent gate.
- **analytics.**
- **notifications_center:** replace the four direct imports with a core `STAFF_NOTIFY` event that it answers, the same inversion as `PRODUCT_CALCULATE_PRICE`. That repays 4 baseline pairs without moving data.

**Result:** 25 apps → 7 (channels, analytics, tracking, notifications_center, plus opt-in importers, dropshipping and cloudflare). The default list loses 17 entries from this cluster.

## Notable problems

### Privacy and consent

**P1. Server-side conversion APIs ignore consent.**
- **Where:** meta_commerce/app.py:47-49 (sends hashed email via services/capi.py:31-50), tiktok_commerce/app.py:44-46, pinterest_commerce/app.py:44-45, snapchat_commerce/app.py:45, reddit_ads/app.py:33.
- **What happens:** the browser pixels are gated (`blocks/*.html`); these server copies are not. A shopper who refused marketing still has their hashed email and purchase sent to five ad networks.
- **Root cause:** orders store no consent snapshot, and `ORDER_PAID` can fire from a payment webhook with no request to read the cookie from.

**P2. `meta.sync_audience` exports the whole user table to Meta.**
- **Where:** meta_commerce/services/audiences.py:32-35 (segment), meta_commerce/agent_tools.py:104 (tool).
- **What happens:** the `all_customers` segment is every `User` with an email, staff included, with no marketing or newsletter filter.
- **Gate:** the tool is scoped `analytics.read` and has no `requires_approval`. A read-only analytics token can call it directly over MCP; only Linda's edge catches it, and only by name.

**P3. tracking's Google Ads purchase conversion bypasses consent, and tracking ships a second cookie banner.**
- **Conversion tag:** tracking/templatetags/tracking.py:234 is called directly by `order_confirmation.html:7` in dot_books, supernatural_shop and montenegro. It loads gtag.js without the `consent.marketing` gate the other seven pixels use.
- **Second banner:** models.py:138 and templatetags/tracking.py:291, rendered by dot_books base.html:702 and supernatural_shop base.html:713. It stores its own localStorage decision, separate from the consent app's cookie.

### Correctness

**P4. Every merchant webhook would be delivered twice.**
- **Where:** core/hooks.py:114 → :262-312 posts each event to every subscribed endpoint; webhooks_ui/app.py:88 subscribes to 12 events and posts again (tasks.py:94).
- **Also:** disabling webhooks_ui does not stop deliveries, because core keeps sending.
- **Status:** latent, because no store has an endpoint yet.

**P5. Ad spend is overstated about 30×.**
- **Cause:** google_shopping/app.py:66 and meta_commerce/app.py:64 contribute a *30-day* spend total. analytics/services_attribution.py:93-99 stores it as *today's* spend, every day. :146-148 then sums 30 of those snapshots, so spend is ~30× too high and ROAS ~30× too low.
- **Also:** Meta spend is keyed `meta` while revenue is keyed by raw utm_source (`facebook`/`ig`), so the two never meet.
- **Also:** the currency is hardcoded `USD` (:99).

**P6. experiments cannot work.**
- `ExperimentsCookieMiddleware` (middleware.py:13) is installed nowhere, so the `morph_visitor` cookie (services.py:49) is never set.
- Without it, variant assignment would change on every request, and the orders code that stamps the visitor id reads a cookie nothing writes.
- `{% variant %}` appears in no template.

**P7. Public claims are made from defaults (the CLAUDE.md "structured data is a public claim" landmine).**
- openai_shopping/feed.py:28-29: every store tells ChatGPT and Perplexity it accepts returns within 30 days, unless the merchant changes it. returns_portal owns that policy.
- openai_shopping/feed.py:87: availability falls back to `in_stock`.
- All six feeds default the feed title to `Dot Books` (google_shopping/services/settings.py:42, the five sibling settings.py files at :25-29, and the app.py schemas). Supernatural, montenegro and irving therefore publish feeds titled "Dot Books".

**P8. External API versions are stale. Verify each against the live API before trusting it.**
- google_shopping/services/ads_api.py:26: Google Ads API **v17**. Google sunsets each version after about a year.
- google_shopping/services/content_api.py:21: Content API **v2.1**, which Google is retiring in favour of the Merchant API.
- importers/adapters/shopify.py:31: Shopify Admin API **2024-01**, no longer supported.
- meta_commerce/services/graph.py:17: Graph API **v21.0**, near the end of its life.

### Security

**P9. SSRF from staff-entered URLs.**
- workflows/engine.py:327-339 POSTs to a staff-entered URL with no `core.net.check_outbound_url`. Both core and webhooks_ui run that check.
- openai_shopping/tasks.py:21-35 has the same gap for `push_endpoint`; it only requires https.

**P10. functions' sandbox cannot stop a runaway function.** In functions/runtime.py:215-219, a timed-out thread keeps running because it cannot be killed. The app is subscribed to both money filters on every store, gated only by a cached `exists()`.

### Performance

**P11. Blocking calls inside the shopper's request.**
- **CAPI sends:** meta, tiktok, pinterest, snapchat and reddit send inline in the `ADD_TO_CART`, `BEGIN_CHECKOUT` and `ORDER_PAID` hooks with `timeout=30` (meta graph.py:72), and write a sync-log row per event. tracking moved its GA4 send to Celery for exactly this reason (tasks.py).
- **workflows:** actions run inline (engine.py:61-63), including `run_agent`.
- **cloudflare:** purges synchronously inside the product-save hook (app.py:55 → services.py:60), before the transaction commits.

**P12. Background churn when nothing is connected.**
- **Catalogue walks:** four 6-hourly feed rebuilds plus `channels.refresh_overview` every 30 min (seven coverage reports, each cached 1 h) add up to about 180 full-catalogue walks a day per store.
- **Wasted warm-up:** the rebuilt feed is cached for 1 h (microsoft_commerce/tasks.py:25, and the same in pinterest, snapchat and tiktok) but rebuilt every 6 h, so the cache is cold 5 hours out of 6.
- **No pruning on any log:**
  - Channel sync logs grow by about 4 rows a day each, forever.
  - `GA4EventLog` has no prune either.
  - `Notification` holds 6,121 rows on dotbooks: `notify_all_staff` (services.py:46-59) writes one row per staff user per stock crossing, with no dedupe.

### Dead settings, and a gap in the guard test

**P13. Seven settings controls have no reader.**
- google_shopping: `currency` (app.py:228) and `free_shipping_over` (app.py:252).
- `country` ("Target country"): meta (app.py:252), microsoft (195), pinterest (216), snapchat (211), tiktok (225).
- **Why the guard misses them:** `core/tests/test_settings_keys_have_readers.py` is textual, and each app's `services/settings.py` `_DEFAULTS` dict mentions the key in quotes, which the test counts as a read. The guard needs to ignore defaults-dict lines.

### Coupling and drift

**P14. Vertical code in default apps.**
- google_shopping/services/mapping.py:20 and plugins/feed_mapping.py:228 query `book_product` without checking `app_registry.is_active`. On 3 of 4 stores that app isn't installed, so every feed build runs one failing query per product.
- reddit_ads/services/book_communities.py:14 ships a list of book subreddits as a Janus tool on a travel marketplace and a survival store.

**P15. Undeclared plugin-to-plugin imports (still in the baseline).**
- channels → analytics (attribution.py:76).
- meta → orders (audiences.py:41).
- google → book_product.
- analytics → orders, consent, notifications_center.
- workflows → agent_core, metafields, notifications_center.
- inventory, orders, analytics, workflows and plugins/context_processors.py:81 → notifications_center. In practice that app is already core.
- dynamics/autopilot.py:155 imports experiments inside try/except, which guards against absence, not disable.
- supernatural_shop cart.html:3 does `{% load experiments %}`, so deleting experiments must remove that line in the same change.

**P16. Lists that will drift.** channels/attribution.py:24-55 hardcodes 8 channel names and a utm map, with openai_shopping missing. analytics keeps a second, raw utm_source mapping (services_attribution.py:63).

**P17. Claims that don't match the code.**
- importers advertises Magento and BigCommerce (app.py description, models.py:22-23) but has no adapter for either.
- WooCommerce works from the CLI only.
- The dashboard hint promises "customers and orders as CSV"; only products exist.
- The Shopify import runs entirely inside the request (views.py:97), under gunicorn's 60 s timeout.
- observability calls itself "the error log" and has none.

### Missing Janus tools

**P18. Merchant actions with no agent tool.** CLAUDE.md requires every merchant action to ship with its Janus tool.
- **Ad campaigns:** all eight ad apps offer create and pause/enable campaign in the dashboard, and google and amazon also offer budget. There are 0 tools for these; every channel tool is read-only except `rebuild_feed` and `sync_audience`.
- **Suppliers:** 0 tools across the four apps for send/pay order, import product, link variant, import tracking.
- **Others with no tool:**
  - webhooks CRUD/replay
  - cloudflare purge
  - importer runs
  - tracking settings and test event
  - notifications list/mark-read
  - workflows create/list
  - openai feed push
  - analytics attribution and cohorts

### Missing tests

**P19. Thin or missing test coverage.**
- **workflows:** the 384-line engine (condition evaluator, five actions) has no test; the only tests check tool registration.
- **webhooks_ui:** 2 tests, none covering fan-out or double delivery.
- **notifications_center:** 1 test.
- **importers:** 2 tests, both Shopify; no CSV or WooCommerce test.
- **tracking:** 6 tests for 1.7k LOC; consent and banner untested.
- **cloudflare:** 12 tests for 1.6k LOC.
