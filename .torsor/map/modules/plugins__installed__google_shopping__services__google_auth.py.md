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

# plugins/installed/google_shopping/services/google_auth.py

Symbols in `plugins/installed/google_shopping/services/google_auth.py`.

- L28 `oauth_config()` (function) — The OAuth client config from PluginConfig (empty strings when unset).
- L40 `is_connected()` (function)
- L45 `has_client()` (function) — True once the OAuth client (id+secret) is set — enough to start consent.
- L51 `authorize_url(redirect_uri: str, state: str='')` (function) — The Google consent URL to start the connect flow, or None if no client.
- L76 `exchange_code(code: str, redirect_uri: str)` (function) — Exchange an auth code for tokens and persist the refresh token.
- L110 `_store_refresh_token(refresh: str)` (function)
- L119 `access_token(*, force: bool=False)` (function) — A valid OAuth2 access token, or None when not configured / on failure.
