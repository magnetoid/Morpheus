# Meta Commerce — Catalog feed + Meta Ads (plugin: `meta_commerce`)

The Meta (Facebook/Instagram) counterpart to `google_shopping`. One plugin owning
the whole Meta surface (clean slate — no existing Meta code, `tracking` is
Google-only): product **Catalog** feed + Catalog API push, **Meta Pixel +
Conversions API**, and the **Marketing API** (campaign reporting + management).

## Boundary
- No overlap with `tracking` (GA4/GTM/Google Ads conversions) — Meta is absent
  there. `meta_commerce` owns the Meta Pixel + CAPI because the pixel's
  `content_ids` must match the catalog feed `id`, so it's catalog-coupled (same
  reasoning that put the Google dynamic-remarketing tag in `google_shopping`).
- Reuse catalog price/image/inventory, `metafields.identifiers` (gtin/mpn),
  `book_product.compat.book_attrs` (brand). Meta-specific per-product overrides
  → `meta.*` metafield namespace (`condition`, `fb_product_category`,
  `google_product_category`, `custom_label_0..4`, `excluded`).

## Connection model (simpler than Google — no OAuth dance)
A long-lived **System User access token** (Business Settings → System Users) +
IDs, all in PluginConfig (never settings.py): `access_token`, `catalog_id`
(feed/Catalog API), `ad_account_id` (Marketing API, `act_…`), `pixel_id`
(Pixel/CAPI), `business_id`. Graph API base `https://graph.facebook.com/v21.0`.

## Phases (each shippable, green on sqlite + CI Postgres)

### Phase 1 — Catalog feed  ⟵ BUILD FIRST
- `services/mapping.py`: `map_product` → Meta catalog attrs (Meta value formats:
  availability `in stock`/`out of stock`, condition `new`, price `9.00 USD`,
  `item_group_id` for variants). Reuses identifiers/book_attrs + `meta.*`
  overrides. Skip when excluded or missing image/price.
- `services/feed.py`: RSS-2.0 `g:`-namespaced XML (Meta ingests the
  Google-format feed in Commerce Manager → Catalog → Data sources). One bad
  product skipped+logged. `MetaSyncLog` audit.
- Endpoint `/feeds/meta-catalog.xml` (cached, busted on product change).
- `contribute_settings_panel` (channels): access_token, catalog_id,
  ad_account_id, pixel_id, business_id, country, currency, defaults, enabled.

### Phase 2 — Dashboard + coverage + agent tools
- `/dashboard/.../meta/` overview: feed URL, coverage report, Catalog API
  push button, connection state. `meta.feed_coverage` / `meta.feed_url` /
  `meta.rebuild_feed` agent tools.

### Phase 3 — Catalog API push
- `services/catalog_api.py`: `POST /{catalog_id}/items_batch`
  (item_type=PRODUCT_ITEM, requests=[{method:UPDATE,data:{…}}]). Beat + button.

### Phase 4 — Meta Pixel + Conversions API
- `templatetags/meta_commerce.py` `{% meta_pixel %}`: base fbq pixel + dynamic
  `content_ids`/`content_type=product`/`value`/`currency` on PDP (ids match the
  feed). Storefront block `global_below_body`. Obeys consent.
- `services/capi.py`: server-side `POST /{pixel_id}/events` (Purchase/AddToCart)
  for iOS-safe attribution; hashed user data. Hooked to ORDER_PAID etc.

### Phase 5 — Marketing API
- `services/ads_api.py`: insights (`/{ad_account_id}/insights` — spend,
  impressions, clicks, purchases, ROAS) + management (pause/activate, create an
  Advantage+ catalog campaign). Dashboard + `meta.ads_report` agent tool.

## House-rule checklist (every phase)
Single AppConfig + manifest; register in MORPHEUS_DEFAULT_APPS; migration
before merge; disable test; secrets only in PluginConfig; ruff + check +
makemigrations + sqlite tests + CI Postgres; mark_safe only with validated/
json-encoded values (Pixel id numeric-validated); docs ship with code.
