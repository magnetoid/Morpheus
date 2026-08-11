# TikTok + Pinterest commerce apps (plugins: `tiktok_commerce`, `pinterest_commerce`)

Two more ad/commerce channel plugins, built on the proven `channel-plugin-pattern`
(see `google_shopping`, `meta_commerce`). Each owns its whole channel; no overlap
with `tracking` (Google-only) or each other. Reuse catalog price/image/inventory,
`metafields.identifiers`, `book_attrs`; per-product overrides via `<channel>.*`
metafield namespace. Thin REST over `requests`, no vendor SDK. Secrets in
PluginConfig only.

## tiktok_commerce — TikTok for Business
- **Catalog feed** `/feeds/tiktok-catalog.xml` (RSS g: — TikTok Catalog Manager
  ingests it). Variant-level item_group_id.
- **Catalog API** push via TikTok Business API v1.3 (feed URL is primary; API push
  optional). Base `https://business-api.tiktok.com/open_api/v1.3/`, auth via
  `Access-Token` header + `advertiser_id` param.
- **TikTok Pixel** (`ttq`) — ViewContent (PDP) + page; **Events API** server-side
  (`/event/track/`) for AddToCart/InitiateCheckout/CompletePayment, content_ids =
  feed id, email/phone hashed. Purchase event_id = order_number for dedup.
- **Ads** — reporting (`/report/integrated/get/`: spend, impressions, clicks,
  conversions, complete_payment, ROAS) + management (campaign status, create).
- Config: access_token, advertiser_id, catalog_id, pixel_code, pixel_enabled.

## pinterest_commerce — Pinterest API v5
- **Catalog feed** `/feeds/pinterest-catalog.xml` (RSS g: — Pinterest Catalogs
  data source). Variant-level item_group_id.
- **Catalogs API** push (v5). Base `https://api.pinterest.com/v5/`, `Bearer` token.
- **Pinterest Tag** (`pintrk`) — pagevisit + viewcategory/viewproduct;
  **Conversions API** (`/ad_accounts/{id}/events`) for add_to_cart / checkout,
  hashed user data, event_id = order_number for dedup.
- **Ads** — reporting (`/ad_accounts/{id}/analytics`: spend, impressions, clicks,
  conversions, ROAS) + management (campaign status, create).
- Config: access_token, ad_account_id, catalog/feed id, tag_id, tag_enabled.

## House-rule checklist (each)
Single AppConfig + manifest; register in MORPHEUS_DEFAULT_APPS; migration
before merge; disable test; secrets in PluginConfig; mark_safe pixel tags
validate the id + json-encode/escape all dynamic values; redact tokens from logs;
contract-test request shaping with mocked HTTP; security + correctness review;
docs + setup guide ship with code. Mirror meta_commerce structure.
