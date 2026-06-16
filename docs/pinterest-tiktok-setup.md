# TikTok + Pinterest commerce — setup guides

Both plugins are built; this is the one-time credential setup, entered in
**Dashboard → Settings → Channels** (stored in PluginConfig, never in the repo).
Each catalog feed works with NO credentials; the API push, pixel/tag and Ads
need the connection.

## TikTok Commerce
1. **Access token** — TikTok for Business → Apps (developers.tiktok.com/apps) →
   create app → get a long-lived access token with `catalog`, `ads_management`
   scopes. → `Access token`.
2. **Advertiser ID** — TikTok Ads Manager (top right). → `Advertiser ID`.
3. **Catalog ID** — TikTok Catalog Manager. → `Catalog ID`.
4. **Pixel code** — TikTok Events Manager → your pixel. → `Pixel code`, then
   enable the pixel toggle.
5. **Feed** — TikTok Catalog Manager → Add catalog → Data feed → paste
   `https://<domain>/feeds/tiktok-catalog.xml`.
6. Verify with the dashboard **Verify connection** button. Events API fires
   AddToCart/InitiateCheckout/CompletePayment server-side automatically.

## Pinterest Commerce
1. **Access token** — Pinterest developers (developers.pinterest.com) → app →
   OAuth token with `catalogs:read/write`, `ads:read/write`, `user_accounts:read`.
   → `Access token (Bearer)`.
2. **Ad account ID** — Pinterest Ads Manager. → `Ad account ID`.
3. **Tag ID** — Pinterest Ads → Conversions → Pinterest Tag. → `Pinterest Tag ID`,
   then enable the tag toggle.
4. **Feed** — Pinterest → Catalogs → Add data source → paste
   `https://<domain>/feeds/pinterest-catalog.xml`.
5. Verify with the dashboard **Verify connection** button. Conversions API fires
   checkout/add_to_cart server-side (checkout deduped against the tag via order id).

Per-product overrides: `tiktok.*` / `pinterest.*` metafield namespaces
(condition, brand, custom_label_*, excluded). See `docs/plans/tiktok-pinterest.md`.

## Microsoft / Bing Commerce
1. **Feed** — Microsoft Merchant Center (ads.microsoft.com → Tools → Merchant
   Center) → Feeds → Create feed → scheduled URL → paste
   `https://<domain>/feeds/microsoft-catalog.xml`.
2. **UET tag** — Microsoft Advertising → Conversion tracking → UET tag → copy the
   numeric **Tag ID** → settings `UET tag ID`, then enable the tag. It fires
   pageLoad everywhere + a purchase event (revenue + order id) on order
   confirmation.
3. Per-product overrides: `microsoft.*` metafield namespace.

**Note:** campaign reporting/management is NOT in this plugin — the Microsoft
Advertising API is SOAP with async reporting, which isn't reliably buildable over
REST. Manage campaigns in Microsoft Advertising; this plugin handles the feed +
conversion tag (the parts that need the storefront).
