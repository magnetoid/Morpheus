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

### Phase 3 — Content API for Shopping (push sync)
- OAuth2 service-account creds (PluginConfig secret refs, never settings.py).
- `services/content_api.py`: batch upsert products to Merchant Center via the
  Content API; `register_celery_beat` periodic push; `GoogleSyncLog` rows.
- Verified-Output rule: confirm `google-api-python-client` (or REST via
  `requests`) — justify the dep in the commit. Prefer thin REST over a heavy SDK.

### Phase 4 — Google Ads layer
- ✅ **Dynamic remarketing tag** (DONE — storefront block `global_below_body`
  + `{% gads_remarketing %}` tag): emits the gtag `page_view` with
  `ecomm_prodid` (= feed `g:id`/sku) / `ecomm_pagetype` / `ecomm_totalvalue` so
  Shopping/PMax build remarketing audiences. Renders nothing until an `AW-` id
  is set + enabled. Obeys Consent Mode v2 set by `tracking` (no extra coupling),
  does NOT duplicate the conversion pixel. XSS-safe: id regex-gated, all values
  json-encoded with `<`/`>`/`&` → `\uXXXX` (security review caught a `</script>`
  break-out via product SKU; fixed + regression-tested).
- **Google Ads API** (TODO — config-gated): Shopping/Performance Max campaign
  create + budget + status, and reporting (impressions/clicks/cost/conv/ROAS) on
  the dashboard. Conversion attribution still flows through `tracking`.

### Phase 3 status — Content API push (DEFERRED, needs creds + dep)
Building it now would mean shipping untested code that requires a new heavyweight
dep (`google-auth` for OAuth2 service-account JWT signing — not currently
installed) with no Merchant credentials to validate against. Per the
Verified-Output rule, deferred until creds exist; the feed URL is the
submission path until then. `requests` is available for a thin REST client when
we do build it.

## House-rule checklist (every phase)
- Single AppConfig + `plugin.py` manifest; register in
  `MORPHEUS_DEFAULT_PLUGINS`; migration before merge.
- Disable test: feed route, dashboard nav, remarketing tag all vanish when off.
- No secrets in `settings.py`; PluginConfig only.
- `ruff`, `manage.py check`, `makemigrations --check`, sqlite tests + CI Postgres.
- Docs: update `docs/PLUGIN_DEVELOPMENT.md` pointer + this file per phase.
