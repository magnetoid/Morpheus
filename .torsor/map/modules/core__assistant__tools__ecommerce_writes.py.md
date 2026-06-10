---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:48'
updated: '2026-06-10T20:08:48'
---

# core/assistant/tools/ecommerce_writes.py

Symbols in `core/assistant/tools/ecommerce_writes.py`.

- L39 `_require_confirmed(confirmed: bool)` (function)
- L44 `_require_hard_gate(*, hard_gate_ack: str, target_name: str, echo: str)` (function) — Enforce the second-tier confirmation for destructive actions.
- L93 `orders_update_status_tool(*, order_number: str, status: str, confirmed: bool=False)` (function)
- L135 `orders_cancel_tool(*, order_number: str, reason: str='', confirmed: bool=False)` (function)
- L184 `orders_add_note_tool(*, order_number: str, note: str, confirmed: bool=False)` (function)
- L228 `products_update_status_tool(*, status: str, id: str='', sku: str='', slug: str='', confirmed: bool=False)` (function)
- L281 `products_update_price_tool(*, price: str, id: str='', sku: str='', slug: str='', variant_id: str='', confirmed: bool=False)` (function)
- L351 `customers_add_note_tool(*, note: str, id: str='', email: str='', confirmed: bool=False)` (function)
- L408 `metafields_set_tool(*, model: str, object_id: str, key: str, value: str, namespace: str='', value_type: str='string', confirmed: bool=False)` (function)
- L461 `metafields_delete_tool(*, model: str, object_id: str, key: str, namespace: str='', confirmed: bool=False, hard_gate_ack: str='', echo: str='')` (function)
- L504 `cms_publish_page_tool(*, id: str='', slug: str='', confirmed: bool=False)` (function)
- L551 `cms_unpublish_page_tool(*, id: str='', slug: str='', confirmed: bool=False)` (function)
