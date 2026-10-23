---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/google_shopping/views.py

Symbols in `plugins/installed/google_shopping/views.py`.

- L18 `google_merchant_feed(request)` (function) — Public Merchant Center feed at /feeds/google-merchant.xml (cached).
- L36 `dashboard(request)` (function) — Feed status + coverage report + submit URL.
- L85 `_content_connected()` (function)
- L92 `_connect_state()` (function) — Where the merchant is in the connect flow, for the dashboard CTA.
- L101 `ads_dashboard(request)` (function) — Google Ads campaign reporting + management.
- L158 `oauth_start(request)` (function) — Kick off the Google consent flow (Content API + Ads).
- L174 `oauth_callback(request)` (function) — Google redirects here with ?code=… — exchange it for a refresh token.
