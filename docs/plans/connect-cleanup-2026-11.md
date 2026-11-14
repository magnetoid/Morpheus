# Connect and clean up: one place for each thing (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status (2026-11-13):** approved by the owner ("Yes, cleanup first"). Branch `feat/connect-cleanup`, stacked on `feat/markets-rates` (PR #162). One release, v0.166.0 (minor: a new page).

**Goal:** Every merchant control does something and lives in one place. Stock gets a page in Products, attribution is one page, and the storefront's settings are honest and guarded.

**Architecture:** No new app, no migration. Each item moves a surface into the app that owns its data, and deletes the second copy or the dead control in the same change. Cross-app data travels on hooks that already exist (`ANALYTICS_AD_SPEND`), never on imports.

**Tech Stack:** Django 6.1, the dashboard registry (`DashboardPage`, `DashboardCard`, `SettingsPanel`), `core.hooks`.

**Spec:** the owner's ask (2026-11-13): "deluje kao da su stvari detached ili su duplirane pages ili su disconnected from features", and the audit that answered it (session notes). There is no separate spec document. Rulings below stand in for one.

## What the audit found, and the ruling on each

| Item | Finding (verified in code) | Ruling |
|---|---|---|
| Rate source, language bar | each had a settings panel apart from its page | **Done in #162** (7c651258) |
| Stock | stock is edited on a product's Stock card and moved on Settings → Shipping → Warehouses; nothing lists stock across products; the low-stock list sits on the Warehouses (settings) page; Stockout forecast is reached only from a card | Task 2: Products → **Inventory** tab with **Stock** (new, carries the low-stock list) and **Forecast** (existing page) |
| storefront schema | `enable_guest_checkout`, `products_per_page`, `show_out_of_stock`, `enable_live_search`, `enable_ai_chat`: no reader, no editor. `maintenance_mode`/`maintenance_message`: read by the middleware, no editor | Task 1: remove the five; Maintenance gets a panel |
| Caching page | 8 of its 25 controls are read by nothing: `asset_max_age_seconds`, `serve_webp`, `responsive_srcset`, `brotli_enabled`, `gzip_enabled`, `min_compress_bytes`, `inline_critical_css`, `warmup_extra_urls` (`morph/settings.py` claims gzip is toggle-gated; it is not) | Task 1: remove them |
| Readers guard | `storefront` sits in `DYNAMIC_READERS`, so its keys escape `core/tests/test_settings_keys_have_readers.py`; the Caching page's keys are not in the schema at all | Task 1: schema lists every key the code reads; storefront leaves `DYNAMIC_READERS` |
| Attribution | Analytics → Attribution (five models, spend from `ANALYTICS_AD_SPEND`, answered by Google and Meta only, each calling its ads API a second time) and Channels → ROAS (spend for eight channels from the channels metrics cache, platform-claimed vs last-touch, blended MER) compute the same thing from two sources. Both store money as `'USD'` on EUR stores | Task 3: one page, Analytics → Attribution; channels answers `ANALYTICS_AD_SPEND` from its cache for every channel; the ROAS page and the Google/Meta handlers go; amounts in the store currency |
| Campaigns | Marketing → Campaigns (hidden) is a read-only list of the same `EmailCampaign` rows Newsletter → Send campaigns lists with actions; Newsletter's "Edit campaigns" button and empty state point to it, and it edits nothing | Task 4: remove the hidden page and the two pointers. The composer is C2 |
| Tracking | Settings → Channels shows **Tracking** (GA4/GTM page) and **Google Ads conversions** (a two-field panel of the same app) side by side | Task 4: the two fields move onto the Tracking page; the panel goes |
| Hidden pages | NPS, Feature adoption, Eco impact and Content audit are reached by their `DashboardCard` (the documented card → report pattern); Google's connect and OAuth pages are flow pages | **No change.** The audit overcounted them; Stockout forecast joins Inventory (Task 2) |
| SEO | SEO → Settings (the `SiteSeoSettings` model) and Settings → Channels → SEO (29 config keys, all read) | **Deferred**: merging needs the schema form renderer moved out of `admin_dashboard` into shared infrastructure, its own patch |

## Global Constraints

- Every changed line traces to a row above. No migrations (`makemigrations --check` stays clean).
- An app's page is a `DashboardPage` contribution; no shell template links an app page (CLAUDE.md, dashboard taxonomy).
- A page that writes needs a capability that `rbac._DEFAULT_TEMPLATES` grants: `inventory.write` for stock, `analytics.read` to read attribution. `CapabilityVocabularyTests` must stay green.
- A removed page takes its `help.md` markers with it (`[…](page:attribution)` in `channels/help.md`); every guide that changes is updated in the same task (`release_notes/tests/test_help_*.py` fail otherwise: markers, headings, developer words).
- Merchant-facing words: "app", Linda for the assistant; no developer words in `help.md`.
- Store writes of stock go through `InventoryService.set_quantity` only (A3 convention).
- Money in the store currency: `core.pricing.store_currency()` (from #162).
- A test that mutates `hook_registry` restores `_handlers[event]` with `addCleanup`; a test that registers a page or panel restores the registry the same way.
- `plugins/installed/admin_dashboard/tests/test_navigation.py` (every tab and tool answers) and `test_disable_guards.py` stay green.
- Run tests with all five opt-in apps when a task touches analytics, channels or navigation (`EXTRA=…booking_marketplace,dsers,zendrop,cjdropshipping,aliexpress`).

## Review Focus

1. **A store with no stock rows, no warehouses or inventory switched off**: the Stock page renders an empty state, and the Inventory tab vanishes when inventory is off. Pinned in Task 2.
2. **A typed stock count that is negative, blank, a decimal or for a switched-off warehouse**: refused with a message, nothing written. Pinned in Task 2.
3. **Channels off, or its cache empty, while analytics is on**: Attribution renders revenue by model with spend blank and says why; nothing raises. Pinned in Task 3.
4. **A stored config key the schema no longer lists** (live stores hold `enable_ai_chat` etc. in `PluginConfig`): nothing reads it, nothing breaks, and the panel never shows it. Pinned in Task 1.
5. **Maintenance mode switched on from the new panel**: shoppers get the maintenance page and staff still reach the dashboard and the store (the middleware's existing rule). Pinned in Task 1.

---

### Task 1: Storefront settings say only what the code reads

**Files:**
- Modify: `plugins/installed/storefront/app.py` (`get_config_schema`, new `contribute_settings_panel`)
- Modify: `plugins/installed/admin_dashboard/views_split/settings.py` (the Caching view: save branches and context), `plugins/installed/admin_dashboard/templates/admin_dashboard/settings_caching.html`
- Modify: `morph/settings.py` (the GZip comment only)
- Modify: `core/tests/test_settings_keys_have_readers.py` (`DYNAMIC_READERS` loses `storefront`)
- Modify: `plugins/installed/storefront/help.md` (Maintenance), `plugins/installed/admin_dashboard/help.md` if it describes the removed caching controls
- Test: `plugins/installed/storefront/tests/test_settings_honest.py` (new)

**Interfaces:**
- Produces: storefront schema keys = `maintenance_mode`, `maintenance_message`, plus every key the Caching page writes and code reads: `html_cache_control`, `graphql_edge_cache_ttl`, `lazy_load_images`, `preload_lcp`, `preconnect_origins`, `dns_prefetch_origins`, `service_worker_enabled`, `offline_page_path`, `defer_non_critical_js`, `font_display`, `preload_fonts`, `home_cache_ttl`, `product_cache_ttl`, `category_cache_ttl`, `search_cache_ttl`, `post_deploy_warmup`, `warmup_top_n`. Each default equals the default its reader uses today (read them from `core/storefront_cache.py`, `storefront/templatetags/caching.py`, `storefront/sw.py`, `storefront/management/commands/warmup_cache.py`, `api/graphql_view.py`); a key whose readers disagree keeps the reader's behaviour and the schema names the Caching page's displayed default.
- Produces: `StorefrontPlugin.contribute_settings_panel() -> SettingsPanel(label='Maintenance', category='general', schema={only maintenance_mode and maintenance_message, with titles and descriptions})`.

- [ ] **Step 1: Write the failing tests** in `test_settings_honest.py`:
  - `test_dead_keys_are_gone`: none of the five dead keys is in `app_registry.get('storefront').get_config_schema()['properties']`.
  - `test_maintenance_panel`: the storefront panel's category is `'general'` and its schema properties are exactly `{'maintenance_mode', 'maintenance_message'}`.
  - `test_maintenance_panel_saves_and_closes_the_shop`: a staff POST through the generic panel save for `storefront` with `maintenance_mode=on` stores True; an anonymous GET of `/` then answers the maintenance page (status and marker the middleware's own tests use); a staff GET of `/dashboard/` still answers.
  - `test_caching_page_has_no_dead_controls`: GET of the Caching page contains none of `name="serve_webp"`, `name="responsive_srcset"`, `name="brotli_enabled"`, `name="gzip_enabled"`, `name="min_compress_bytes"`, `name="inline_critical_css"`, `name="asset_max_age_seconds"`, `name="warmup_extra_urls"`, and still contains `name="lazy_load_images"` and `name="home_cache_ttl"`.
  - `test_caching_save_keeps_working`: POSTs of `save_assets`, `save_critical` and `save_warmup` store their live keys and none of the removed ones; a POST of `action=save_compression` (the action is gone) changes nothing.
  - `test_stale_stored_keys_are_harmless`: a `PluginConfig` row for `storefront` holding `enable_ai_chat=False` and `serve_webp=False` renders `/`, the Caching page and the General settings category with 200.
- [ ] **Step 2: Run them** (`WT=$PWD/wt-clean zsh t.sh plugins.installed.storefront.tests.test_settings_honest`); expect failures on the panel and the dead controls.
- [ ] **Step 3: Implement.** Schema as above; panel; delete the eight controls from the template and their `set_config` lines from the view (the "Compression" card goes whole, since none of its three controls does anything; Cloudflare and nginx compress). Fix the `morph/settings.py` comment to say GZip always runs. Remove `'storefront'` from `DYNAMIC_READERS`.
- [ ] **Step 4: Run** the new tests, `core.tests.test_settings_keys_have_readers`, `plugins.installed.storefront`, `plugins.installed.admin_dashboard.tests.test_navigation`, the help tests `plugins.installed.release_notes`. All pass.
- [ ] **Step 5: Commit** `fix: storefront settings say only what the code reads (maintenance gets a panel, dead caching controls go)`.

### Task 2: Products → Inventory (Stock and Forecast)

**Files:**
- Create: `plugins/installed/inventory/stock_page.py` (view + form handling), `plugins/installed/inventory/templates/inventory/dashboard/stock.html`
- Modify: `plugins/installed/inventory/services.py` (`stock_rows()`; `low_stock_levels` built on it), `plugins/installed/inventory/app.py` (`contribute_dashboard_pages`: new Stock page; Stockout forecast leaves `nav='hidden'`; the home hook adds `low_stock_url`), `plugins/installed/inventory/dashboard.py` + `templates/inventory/dashboard/warehouses.html` (the low-stock section moves to Stock), `plugins/installed/admin_dashboard/templates/admin_dashboard/home.html` (the Stock alerts tile links `{{ low_stock_url }}`, "See all"), `plugins/installed/ai_assistant/services/pulse.py` (the low-stock card's url), `plugins/installed/inventory/help.md`
- Modify: `plugins/installed/inventory/tests/test_low_stock_list.py` (the list now lives on Stock)
- Test: `plugins/installed/inventory/tests/test_stock_page.py` (new)

**Interfaces:**
- Consumes: `InventoryService.set_quantity(variant, warehouse, quantity, *, reason, reference, user)`; `StockLevel(variant, warehouse, quantity, reserved_quantity, reorder_point)`; `Warehouse.is_active`; `low_stock_threshold()`; `paginate_and_sort` the way `crm/views.py` imports it.
- Produces: `inventory.services.stock_rows() -> QuerySet[StockLevel]`: switched-on warehouses, products that count stock, annotated `free = quantity − reserved_quantity`, `select_related('variant__product', 'warehouse')`. `low_stock_levels(limit)` = `stock_rows().filter(free__lte=low_stock_threshold())` in its current order (one rule for the home tile, Pulse and the Stock page). Low-stock URL: `/dashboard/apps/inventory/stock/?status=low`.
- Produces: `DashboardPage(label='Stock', slug='stock', section='products', group='Inventory', order=70, icon='boxes', view='plugins.installed.inventory.stock_page.stock_view')` and the forecast page as `DashboardPage(label='Forecast', slug='stockout-forecast', section='products', group='Inventory', order=71, …)` (same slug, so its URL, its card link and the home link keep working).

- [ ] **Step 1: Write the failing tests** (`test_stock_page.py`), each on a product with `track_inventory=True`, one variant, two warehouses (one switched off):
  - `test_lists_counted_stock`: GET `/dashboard/apps/inventory/stock/` as staff shows the product name, the SKU and the active warehouse's on-hand count; the switched-off warehouse's row is not listed; a product with `track_inventory=False` is not listed.
  - `test_status_filter`: with the threshold at 5, a row with 0 free shows under `?status=out` and `?status=low`, a row with 3 free only under `?status=low`, a row with 9 free under neither; the pills read Out / Low.
  - `test_one_low_rule`: the rows under `?status=low` are exactly `low_stock_levels()`'s; the Warehouses page no longer carries `id="low-stock"`; Pulse's low-stock card and the home tile's link name the Stock page's low filter.
  - `test_search`: `?q=<sku>` and `?q=<part of the name>` find the row; `?q=zzz` shows the empty state.
  - `test_set_on_hand`: a POST `{level: <StockLevel id>, quantity: '12'}` sets the count to 12 and leaves one `StockMovement` (through `set_quantity`); the response redirects back with the filters kept.
  - `test_refuses_bad_counts`: `'-1'`, `''`, `'2.5'`, `'abc'`, and a level in a switched-off warehouse each leave the count unchanged and show an error message.
  - `test_empty_store`: no stock rows → 200 with the empty-state marker (`data-empty="stock"`).
  - `test_boundaries`: anonymous GET → redirect to sign-in; anonymous POST changes nothing; a staff user without `inventory.write` under rbac `enforce` gets 403 on POST (follow the permission-boundary-tests skill's pattern used in `inventory/tests/test_warehouses_page.py`).
  - `test_tab_group`: `navigation.tabs(staff)` for section `products` has one `Inventory` tab whose sub-tabs are Stock and Forecast; with inventory switched off neither appears.
- [ ] **Step 2: Run them**; expect 404s.
- [ ] **Step 3: Implement** the view: GET needs `inventory.read`, POST `inventory.write` (`require_capability` per method, the way `inventory/dashboard.py` gates); rows from `stock_rows()`; filters `status` (`low` = free ≤ `low_stock_threshold()`, `out` = free ≤ 0), `warehouse`, `q` (name or SKU, case-insensitive); sort by product name; `paginate_and_sort` (50 a page). Each row: product name linked to its editor, variant name (hidden when the variant is the default one), SKU, warehouse, an on-hand number input with a Save button (one small form per row), reserved, available, reorder point, a status pill. Template extends `admin_dashboard/base.html`, uses existing utility classes only (the dashboard's Tailwind is prebuilt: reuse classes already on the warehouses page; if a new class is needed, run the build per CLAUDE.md).
- [ ] **Step 4: Update `help.md`**: Stock and Forecast under Products → Inventory, with `page:` markers; "To change a count, type it on [Stock](page:stock) or on the product's Stock card." Linda: `inventory.set_stock` already does the same write; say so in the guide's Linda line if the guide has one.
- [ ] **Step 5: Run** `plugins.installed.inventory`, `plugins.installed.admin_dashboard.tests.test_navigation`, `admin_dashboard.tests.test_tailwind_build`, `release_notes`. All pass.
- [ ] **Step 6: Commit** `feat: Products → Inventory lists stock across products and takes counts (Stock), with the forecast beside it`.

### Task 3: One attribution page

**Files:**
- Modify: `plugins/installed/channels/app.py` (answer `ANALYTICS_AD_SPEND`; remove the ROAS `DashboardPage`), `plugins/installed/channels/views.py` (remove `attribution_view`), `plugins/installed/channels/help.md`
- Delete: `plugins/installed/channels/attribution.py`, `plugins/installed/channels/templates/channels/attribution.html`, the channels tests that cover only the removed page
- Modify: `plugins/installed/google_shopping/app.py`, `plugins/installed/meta_commerce/app.py` (drop `_ad_spend` and its `register_hook`)
- Modify: `plugins/installed/analytics/services_attribution.py` (store currency; platform columns; blended MER), `plugins/installed/analytics/views_attribution.py`, `plugins/installed/analytics/templates/analytics/attribution.html`, `plugins/installed/analytics/help.md`
- Modify: `core/hooks.py` (the `ANALYTICS_AD_SPEND` comment: who answers, row shape)
- Modify: `scripts/plugin_boundary_baseline.json` via `python scripts/check_plugin_boundary.py --save` if the channels → analytics pair disappears
- Test: `plugins/installed/channels/tests/test_ad_spend_answer.py`, `plugins/installed/analytics/tests/test_attribution_page.py` (new)

**Interfaces:**
- Produces: channels' `ANALYTICS_AD_SPEND` handler appends, for each cached metrics row with a spend, `{'channel': <key>, 'spend': <number>, 'conversions': <int|None>, 'platform_revenue': <number|None>, 'days': 30}` where key maps `google_shopping→google`, `meta_commerce→meta`, `tiktok_commerce→tiktok`, `pinterest_commerce→pinterest`, `microsoft_commerce→microsoft`, `amazon_ads→amazon`, `reddit_ads→reddit`, `snapchat_commerce→snapchat` (the keys analytics' journeys use).
- Produces: `analytics.services_attribution._channel_of` folds the utm spellings channels used to map (`googleads`, `google_ads`, `gads` → `google`; `facebook`, `fb`, `instagram`, `ig` → `meta`; `bing` → `microsoft`; `snap` → `snapchat`).
- Produces: `roas_by_channel(model, days=30) -> list[dict]` rows gain `platform_revenue` and `conversions` (from the newest `AdSpendSnapshot.source_meta`); the view adds `total_revenue_store` (all purchase revenue in the window, from analytics' own events) and `blended_mer` = that ÷ total spend.
- Produces: `AdSpendSnapshot.spend` and attribution `DailyMetric.value_money` in `store_currency()`.

- [ ] **Step 1: Write the failing tests.**
  - channels `test_ad_spend_answer`: with the metrics cache holding Google (spend 120, revenue 300, conversions 4) and TikTok (spend 0), `hook_registry.filter(ANALYTICS_AD_SPEND, value=[])` returns one Google row with key `google` and those numbers; with the cache empty it returns `[]`; with channels switched off it returns `[]`; google_shopping and meta_commerce add no row of their own (assert exactly one row while both apps are on).
  - analytics `test_attribution_page`: after `collect_ad_spend()` (channels answering from a seeded cache) and `attribute_revenue()` on two purchases (one from `utm_source=googleads`, one direct), GET `/dashboard/apps/analytics/attribution/` shows the Google row with spend, platform-claimed revenue and the model's attributed revenue, the blended MER, and the amounts in the store currency (set `STORE_CURRENCY='EUR'` and assert `€` or `EUR` per the dashboard's money filter); `?model=linear` changes the attributed column; with channels off the page renders, shows revenue by model and the note that spend comes from the Channels app.
  - `test_roas_page_is_gone`: `/dashboard/apps/channels/attribution/` answers 404, and `navigation.tabs()` for section `channels` has no ROAS tab.
- [ ] **Step 2: Run them**; expect failures.
- [ ] **Step 3: Implement** as in Interfaces. The view stays read-only. Keep the five models and their labels. Delete the ROAS page, view, template and module; remove the `[Channel ROAS & attribution](page:attribution)` line from `channels/help.md`; `analytics/help.md` describes the one page: spend and platform-claimed revenue per channel (from the Channels app), revenue by the chosen model, ROAS, blended MER.
- [ ] **Step 4: Run** `plugins.installed.analytics plugins.installed.channels plugins.installed.google_shopping plugins.installed.meta_commerce plugins.installed.admin_dashboard.tests.test_navigation plugins.installed.release_notes core.tests.test_hook_disable_gating` with all opt-in apps; `python scripts/check_plugin_boundary.py` (save the baseline if it reports a stale pair). All pass.
- [ ] **Step 5: Commit** `fix: one attribution page (Analytics), ad spend from the Channels app for every channel, in the store currency`.

### Task 4: Tracking in one place; the campaigns duplicate goes

**Files:**
- Modify: `plugins/installed/tracking/app.py` (remove `contribute_settings_panel`; keep the schema), the Tracking page view and template (two fields: Google Ads conversion ID and purchase label, saved with `set_config`), `plugins/installed/tracking/help.md`
- Modify: `plugins/installed/marketing/app.py` (remove the hidden Campaigns page), `plugins/installed/marketing/dashboard.py` (remove `campaigns_list` if nothing else uses it), `plugins/installed/marketing/help.md` if it names the page
- Modify: `plugins/installed/newsletter/templates/newsletter/dashboard/campaigns.html` (remove the "Edit campaigns" button; the empty state says "No campaigns yet." and nothing about Marketing → Campaigns), `plugins/installed/newsletter/help.md` if it points there
- Test: `plugins/installed/tracking/tests/test_ads_fields_on_page.py`, `plugins/installed/newsletter/tests/test_campaigns_page_links.py` (new)

- [ ] **Step 1: Write the failing tests.**
  - tracking: `app_registry.settings_panel('tracking')` is None; GET `/dashboard/tracking/` shows inputs named `google_ads_conversion_id` and `google_ads_purchase_label` with the stored values; a staff POST saves both (the conversion tag test that already reads them still passes); an anonymous POST saves nothing.
  - newsletter/marketing: GET of Newsletter → Send campaigns has no `/dashboard/apps/marketing/campaigns/` link; `/dashboard/apps/marketing/campaigns/` answers 404; no tab named Campaigns under Marketing other than the newsletter one.
- [ ] **Step 2: Run them**; expect failures.
- [ ] **Step 3: Implement.** The Tracking page's save handler gains the two keys (strip, keep blank as blank); the panel method goes.
- [ ] **Step 4: Run** `plugins.installed.tracking plugins.installed.marketing plugins.installed.newsletter plugins.installed.admin_dashboard.tests.test_navigation plugins.installed.release_notes`. All pass.
- [ ] **Step 5: Commit** `fix: Google Ads conversion fields on the Tracking page, and the read-only campaigns copy goes`.

### Task 5: Release

- [ ] `python manage.py release --minor "Every control in one place, and stock gets its own page" -m …` (one bullet per task, merchant words; base `RELEASE_CHECK_BASE=origin/feat/markets-rates`).
- [ ] `docs/ARCHITECTURE.md` only if a subsystem's job changed (attribution's data path does: one sentence).
- [ ] Gates: ruff 0.15.8 check + format, bandit `-ll`, `manage.py check`, `makemigrations --check --dry-run`, the three boundary scripts, `release --check`, the pytest smoke suites, and the full serial suite with all five opt-in apps.
- [ ] Final whole-branch review on the most capable model; one fix round; then the stacked PR on #162.
