---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/installed/tiktok_commerce/services/api.py

Symbols in `plugins/installed/tiktok_commerce/services/api.py`.

- L20 `creds()` (function)
- L31 `has_token()` (function)
- L35 `ads_connected()` (function)
- L40 `catalog_connected()` (function)
- L45 `_headers()` (function)
- L49 `_unwrap(resp)` (function) — TikTok wraps everything in {code, message, data}; code 0 = success.
- L57 `get(path: str, params: dict | None=None)` (function)
- L71 `post(path: str, payload: dict)` (function)
- L85 `verify_connection()` (function) — Validate the token + advertiser via real API calls. {check: {ok, detail}}.
- L105 `_err(e)` (function)
