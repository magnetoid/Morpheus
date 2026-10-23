---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/amazon_ads/services/api.py

Symbols in `plugins/installed/amazon_ads/services/api.py`.

- L24 `creds()` (function)
- L32 `base_url()` (function)
- L36 `ads_connected()` (function)
- L40 `_headers(extra: dict | None=None)` (function)
- L55 `request(method: str, path: str, *, json_body=None, headers_extra=None)` (function) — REST call to the Ads API. Returns {ok, data} or {ok: False, reason}.
- L76 `list_profiles()` (function) — GET /v2/profiles — used to discover/verify the profile_id.
- L100 `verify_connection()` (function) — Validate token + profile via GET /v2/profiles. {check: {ok, detail}}.
- L127 `_err(e)` (function)
