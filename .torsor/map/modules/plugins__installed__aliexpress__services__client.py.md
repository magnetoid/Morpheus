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

# plugins/installed/aliexpress/services/client.py

Symbols in `plugins/installed/aliexpress/services/client.py`.

- L44 `AEError` (class)
- L45 `__init__(self, message: str, code: str='')` (method)
- L51 `_plugin()` (function)
- L57 `config()` (function)
- L68 `app_credentials()` (function)
- L73 `sign(secret: str, params: dict, api_path: str='')` (function) — The IOP signature: HMAC-SHA256 over [path] + sorted key+value pairs, upper hex.
- L81 `_value(v)` (function)
- L89 `unwrap(node: Any)` (function) — Strip ``<method>_response`` and single-key list wrappers, recursively.
- L104 `_post(url: str, data: dict)` (function)
- L126 `_system(api_path: str, params: dict)` (function)
- L138 `_store_tokens(body: dict)` (function)
- L154 `exchange_code(code: str)` (function) — OAuth step 2: the code from the callback → tokens, stored.
- L159 `refresh_tokens()` (function)
- L166 `connection()` (function)
- L176 `disconnect()` (function)
- L188 `access_token()` (function)
- L199 `call(method: str, params: dict | None=None, *, token: bool=True)` (function) — Call business ``method``; returns the unwrapped payload.
