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

# plugins/installed/cjdropshipping/views.py

Symbols in `plugins/installed/cjdropshipping/views.py`.

- L24 `_context(request: HttpRequest)` (function)
- L65 `dashboard(request)` (function)
- L72 `test_connection_view(request)` (function)
- L99 `register_webhooks_view(request)` (function)
- L119 `import_product_view(request)` (function)
- L145 `send_order_view(request, order_number: str)` (function)
- L165 `pay_order_view(request, order_number: str)` (function)
- L181 `sync_view(request)` (function)
- L196 `webhook_view(request)` (function) — CJ's push. Always 200 (CJ closes a topic that fails); only a verified message acts.
