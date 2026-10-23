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

# plugins/installed/cjdropshipping/services/webhooks.py

Symbols in `plugins/installed/cjdropshipping/services/webhooks.py`.

- L38 `signature(body: bytes, open_id: str)` (function)
- L43 `verify(body: bytes, sign: str, open_id: str)` (function)
- L49 `register(url: str, *, enable: bool=True)` (function)
- L58 `_record_for(*, cj_order_id: str='', order_numbers=())` (function)
- L73 `_first_seen(message_id: str)` (function) — CJ keeps ``messageId`` across retries; apply each message once.
- L82 `apply(message: dict)` (function) — Apply one verified message; returns what happened, for the log.
- L92 `_apply_order(params: dict)` (function)
- L115 `_apply_logistic(params: dict)` (function)
- L133 `_apply_stock(params: dict)` (function)
- L150 `_apply_variant(params: dict)` (function)
