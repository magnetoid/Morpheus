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

# plugins/installed/meta_commerce/services/graph.py

Symbols in `plugins/installed/meta_commerce/services/graph.py`.

- L21 `creds()` (function)
- L32 `has_token()` (function)
- L36 `catalog_connected()` (function)
- L41 `ads_connected()` (function)
- L46 `get(path: str, params: dict | None=None)` (function) — GET {GRAPH}/{path}. Returns {ok, data} or {ok: False, reason}.
- L63 `post(path: str, payload: dict)` (function) — POST {GRAPH}/{path} (form-encoded). Returns {ok, data} or {ok: False}.
- L80 `verify_connection()` (function) — Make real Graph calls to validate each credential — far stronger than the
- L127 `_err(e)` (function)
- L138 `_redact(s: str)` (function) — Strip any access_token=… from a string before it reaches a log — the
