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

# plugins/installed/cjdropshipping/services/client.py

Symbols in `plugins/installed/cjdropshipping/services/client.py`.

- L37 `CJError` (class)
- L38 `__init__(self, message: str, code: int | None=None)` (method)
- L44 `config()` (function)
- L57 `api_key()` (function)
- L61 `_key_id(key: str)` (function)
- L65 `_throttle()` (function)
- L75 `_parse(resp)` (function)
- L87 `credentials(*, force: bool=False)` (function) — ``{'access_token', 'open_id'}`` for the configured API key.
- L121 `open_id()` (function) — The account's openId — the secret CJ signs its webhooks with.
- L126 `request(method: str, path: str, *, params: dict | None=None, json: Any=None)` (function) — Call ``path`` and return ``data``; raises :class:`CJError`.
