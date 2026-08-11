# Google Shopping — Merchant Center feed + Google Ads (plugin: `google_shopping`)

**Goal:** an extensive, powerful Google Merchant Center + Google Ads capability,
delivered as ONE Morpheus plugin following the house rules (plugin owns all its
code; contributes, never edits sibling layers; disable-safe).

## Boundary (audited 2026-06-15 — see overlap notes)

- **`tracking` plugin OWNS Google Ads conversion pixel + GA4 + GTM + Consent
  Mode.** `google_shopping` must NOT emit conversion tags — it complements with
  the *dynamic remarketing* tag (product-id payload) and campaign management.
- **`seo` plugin OWNS** sitemaps + Product JSON-LD + AI feeds. `google_shopping`
  adds the Merchant Center RSS-2.0 `g:`-namespace product feed (distinct format).
- **Reuse, don't re-model:** `product.primary_image`, `price`,
  `compare_at_price`→sale_price, inventory `StockLevel`→availability,
  `metafields.identifiers` (isbn13/ean13/upc/gtin14/mpn)→gtin/mpn,
  `book_product.compat.book_attrs` (publisher→brand, language, etc.).
- **Google-specific attributes that have no home → metafield namespace
  `google.*`** (no schema migration): `condition`, `google_product_category`,
  `custom_label_0..4`, `gender`, `age_group`, `excluded` (feed opt-out).
  Defaults come from the settings panel; per-product metafield overrides win.

## Model (one small table — keep sqlite/Postgres FK-type safe)

`GoogleSyncLog` — audit row per feed build / Content-API push: `kind`
(feed|content_api|ads), `status`, `item_count`, `errors` (JSON), `message`,
`created_at`. That's the only model in Phase 1–2. Everything else is config
(PluginConfig JSON) + computed.

## Phases (each independently shippable + green on sqlite AND CI Postgres)

### Phase 1 — Merchant Center product feed  ⟵ BUILD FIRST
- `services/feed.py`: `build_feed(channel=None) -> str` renders the Google
  Merchant **RSS 2.0** XML with the `g:` namespace. One `<item>` per
  feed-eligible active product (and per *variant* when variable): `g:id`,
  `title`, `description`, `link`, `g:image_link`, `g:additional_image_link`,
  `g:availability`, `g:price`, `g:sale_price`, `g:brand`, `g:gtin`/`g:mpn`,
  `g:identifier_exists`, `g:condition`, `g:google_product_category`,
  `g:product_type`, `g:custom_label_0..4`, shipping weight, `g:item_group_id`
  for variants. Book products: also `g:product_type` from genre path.
- `services/mapping.py`: `map_product(product) -> dict | None` — the single
  source of feed-field resolution (identifiers→gtin, book_attrs→brand,
  metafield `google.*` overrides, settings defaults). Returns None (skip) when
  excluded or missing a hard-required attr.
- Endpoint `register_urls`: `/feeds/google-merchant.xml` (cached; cache busted
  on PRODUCT_CREATED/UPDATED/DELETED hooks). Optional `?channel=<slug>` for
  multi-channel later.
- `contribute_settings_panel` (category `channels`): `enabled`, `merchant_id`,
  `country`, `language`, `currency`, `default_brand`,
  `default_google_product_category`, `default_condition`, `free_shipping_over`,
  `include_out_of_stock`, `feed_title`, `feed_description`.
- Tests: feed validates (well-formed XML, required attrs present, sale_price
  only when on sale, variant item_group_id, excluded product skipped,
  out-of-stock honoring the flag). Contract: assert against the real Product +
  metafields, not mocks.
- **Success:** `curl /feeds/google-merchant.xml` → valid Merchant XML with every
  eligible product; one bad product never 500s the feed (skipped + logged).

### Phase 2 — Feed dashboard + coverage/validation + agent tools
- Dashboard page `/dashboard/google/`: status (last build, item count),
  **coverage report** (eligible vs total; per-attribute completeness: image,
  price, gtin/identifier, brand, gpc), validation warnings per Google spec,
  download link, "rebuild now".
- `contribute_agent_tools`: `google.feed_coverage` (audit), `google.feed_url`,
  `google.rebuild_feed`. Lets Linda answer "how many products aren't
  Shopping-eligible and why."
- Disable-guard test (plugin off → nav/route/feed all gone).

### Phase 3 — Content API for Shopping (push sync)  ✅ DONE
- `services/google_auth.py`: OAuth2 **refresh-token** flow (client_id/secret/
  refresh_token → access_token, cached) — thin REST over `requests`, NO
  google-auth/SDK dep, no JWT signing. Creds in PluginConfig only.
- `services/content_api.py`: batch-upserts every eligible product to Merchant
  Center via the Content API v2.1 `products/batch` endpoint; `GoogleSyncLog`
  rows; "Push now" button on the dashboard; `register_celery_beat` 6-hourly push
  (`tasks.py`). Graceful no-op when not connected.
- Verified-Output: `requests` (already a dep) only; request-shaping
  contract-tested against the real API resource format with mocked HTTP.

### Phase 4 — Google Ads layer
- ✅ **Dynamic remarketing tag** (DONE — storefront block `global_below_body`
  + `{% gads_remarketing %}` tag): emits the gtag `page_view` with
  `ecomm_prodid` (= feed `g:id`/sku) / `ecomm_pagetype` / `ecomm_totalvalue` so
  Shopping/PMax build remarketing audiences. Renders nothing until an `AW-` id
  is set + enabled. Obeys Consent Mode v2 set by `tracking` (no extra coupling),
  does NOT duplicate the conversion pixel. XSS-safe: id regex-gated, all values
  json-encoded with `<`/`>`/`&` → `\uXXXX` (security review caught a `</script>`
  break-out via product SKU; fixed + regression-tested).
- ✅ **Google Ads API** (DONE — `services/ads_api.py`, REST v17 over `requests`,
  shares the OAuth token): campaign **reporting** via GAQL `searchStream`
  (cost/clicks/impressions/conversions/value/ROAS per campaign + totals) and
  **management** (pause/enable + set budget via `campaigns:mutate` /
  `campaignBudgets:mutate`). Surfaced on a `/dashboard/.../ads/` page (date
  range, KPI row, per-campaign table with pause/enable) + `google.ads_report`
  agent tool. Config-gated (developer token + customer id + OAuth); renders a
  "connect Google Ads" state when not connected. Conversion attribution still
  flows through `tracking`. Request-shaping contract-tested with mocked HTTP.

**Connection model:** one OAuth2 refresh token (client_id/secret/refresh_token)
authorises BOTH the Content API (Merchant) and the Ads API; Ads also needs a
developer token + customer id. All in PluginConfig, never settings.py.

### Phase 5 — one-click connect + lifecycle completion (DONE)
- ✅ **"Connect with Google" OAuth flow** (`google_auth.authorize_url` /
  `exchange_code` + `views.oauth_start`/`oauth_callback`, hidden dashboard
  pages): merchant adds only the OAuth client id+secret, clicks Connect, grants
  Merchant+Ads in one consent (`access_type=offline`, `prompt=consent`), and the
  refresh token is captured automatically. **Anti-CSRF `state`** stored in
  session + verified in the callback (blocks login-CSRF). No manual refresh-token
  dance.
- ✅ **Shopping campaign creation** (`ads_api.create_shopping_campaign`): budget
  + campaign mutate, PAUSED by default, tied to the Merchant feed. Create form on
  the Ads dashboard. → Ads is now full create/read/update.
- ✅ **Merchant Center diagnostics** (`content_api.product_statuses`): live
  active/pending/disapproved counts + top item-level issues on the feed
  dashboard + `google.merchant_diagnostics` agent tool. → the "why is my product
  disapproved" loop.

Total: 39 tests; 5 agent tools; security-reviewed (+ state-CSRF); all live.

## House-rule checklist (every phase)
- Single AppConfig + `app.py` manifest; register in
  `MORPHEUS_DEFAULT_APPS`; migration before merge.
- Disable test: feed route, dashboard nav, remarketing tag all vanish when off.
- No secrets in `settings.py`; PluginConfig only.
- `ruff`, `manage.py check`, `makemigrations --check`, sqlite tests + CI Postgres.
- Docs: update `docs/PLUGIN_DEVELOPMENT.md` pointer + this file per phase.
