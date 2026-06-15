# Meta Commerce — merchant setup guide

Connect the `meta_commerce` plugin to Meta (Facebook/Instagram) Commerce + Ads.
The plugin is fully built; this is the one-time credential setup, all entered in
**Dashboard → Settings → Channels → Meta Commerce** and stored in PluginConfig
(never in `settings.py` or the repo).

## What you get

- **Catalog feed** at `https://<domain>/feeds/meta-catalog.xml` — add it as a
  data source in Commerce Manager, or let the **Catalog API** push directly.
- **Meta Pixel** on the storefront (PageView + dynamic ViewContent whose
  `content_ids` match the catalog) + **Conversions API** server-side Purchase.
- **Meta Ads** — campaign reporting (spend/clicks/purchases/ROAS), pause/activate,
  and create a paused catalog-sales campaign.

The feed works with **no credentials**; the API push, Pixel and Ads need the
connection below.

## 1. A System User access token (Business Settings)

1. <https://business.facebook.com/> → **Business Settings → Users → System Users**
   → add a system user (Admin) → **Generate new token**.
2. App: your Meta app. Scopes: **`catalog_management`, `ads_management`,
   `business_management`**. Generate a **long-lived** token and copy it.
3. Assign the system user to your **Catalog**, **Ad Account**, and **Pixel** under
   Business Settings → Data sources / Accounts.

Paste the token into `System User access token`.

## 2. IDs

- **Catalog ID** — Commerce Manager → Catalog → Settings (or the URL). →
  `Catalog ID`.
- **Ad account ID** — Ads Manager (`act_1234…`; digits or `act_` both fine) →
  `Ad account ID`.
- **Pixel ID** — Events Manager → your pixel → `Pixel ID`.
- **Business ID** (optional) → `Business ID`.

## 3. Submit / sync the catalog

- **Manual:** Commerce Manager → Catalog → **Data sources → Add → Scheduled feed**
  → paste the feed URL.
- **API:** on **Dashboard → Meta Commerce**, click **Push now** (or let the
  6-hourly background sync run).

## 4. Turn on the Pixel

Set **Enable Meta Pixel on the storefront** in settings. The pixel fires
PageView everywhere and ViewContent on PDPs with `content_ids` = the catalog
`id`, so dynamic/Advantage+ catalog ads line up. The Conversions API Purchase
event fires automatically on order payment (email is SHA-256 hashed).

## 5. Per-product overrides (optional)

`meta.*` metafield namespace: `meta.condition`, `meta.fb_product_category`,
`meta.google_product_category`, `meta.brand`, `meta.custom_label_0..4`,
`meta.excluded` (truthy to keep a product out of the feed).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Feed URL 404 | Feed disabled — enable it in settings. |
| Push “not connected” | Set the access token + catalog ID. |
| Ads page “connect” | Set the access token + ad account ID. |
| Pixel not firing | Enable the pixel toggle; the id must be numeric. |
| Feed stale after deploy | Redis cache survives deploys — hit **Rebuild feed**. |

See `docs/plans/meta-commerce.md` for the full design and the boundary with the
`tracking` (Google) plugin.
