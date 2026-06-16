# Reddit Ads app (plugin: `reddit_ads`)

Book-relevant channel (r/books, r/Fantasy, r/RomanceBooks…). Full parity minus a
catalog feed (Reddit has no off-Reddit shopping feed):
- Auth: Reddit OAuth2 refresh-token (HTTP-basic client) → access token; required
  User-Agent header. Token endpoint www.reddit.com/api/v1/access_token.
- **Reddit Pixel** (rdt): PageVisit + ViewContent (PDP) + Purchase (confirmation,
  conversion_id = order_number for dedup).
- **Conversions API** (server-side): Purchase/AddToCart, hashed email,
  conversion_id = order_number. Base ads-api.reddit.com.
- **Ads API v3**: campaign list / pause / enable / create + reporting.
- Dashboard + agent tools. Best-effort until validated with live creds.
