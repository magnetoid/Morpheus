# Amazon Ads app (plugin: `amazon_ads`)

Amazon is structurally different from the shopping-feed channels:
- **No off-Amazon shopping feed** — listing products *on* Amazon is the Selling
  Partner API (SP-API), a separate full marketplace integration (SigV4 + feed
  documents + listings/inventory/orders). Out of scope here.
- **No simple public conversion pixel** — Amazon Attribution is ad-side tags.

So this app is **Amazon Advertising API** (clean REST):
- Auth: Login with Amazon OAuth2 refresh-token → access token. Headers:
  Authorization: Bearer, Amazon-Advertising-API-ClientId, -Scope (profile_id).
  Region base: NA `advertising-api.amazon.com`, EU `-eu`, FE `-fe`.
- **Campaign management** (Sponsored Products v3): list / pause / enable / create.
- **Reporting** (async v3): create report → poll → download GZIP JSON → parse →
  cache (Celery task). Same fail-soft pattern as microsoft_commerce reporting.
- Dashboard (campaigns + metrics + management) + agent tools.
- Best-effort until validated with live credentials (v3 shapes from docs).
