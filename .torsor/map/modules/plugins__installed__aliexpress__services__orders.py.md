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

# plugins/installed/aliexpress/services/orders.py

Symbols in `plugins/installed/aliexpress/services/orders.py`.

- L54 `_bool(key: str, default: bool)` (function)
- L59 `_country_code(raw)` (function)
- L70 `lines_for(order)` (function) — ``[{link, quantity}]`` for the order's AliExpress-linked shippable items.
- L92 `orders_to_send()` (function)
- L98 `_service_for(line: dict, country: str)` (function)
- L113 `_payload(order, lines: list[dict])` (function)
- L152 `_claim(order)` (function)
- L166 `_fail(record, message: str)` (function)
- L173 `forward_order(order)` (function) — Place ``order`` on AliExpress (idempotent). Returns the AEOrder, or None if already placed.
- L212 `_mark_processing(order)` (function)
- L224 `_tracking_url(tracking: str)` (function)
- L230 `ship(record)` (function) — Ship the store order once every AliExpress order of it has a tracking number.
- L257 `_order_status(ae_order_id: str)` (function)
- L264 `_tracking(ae_order_id: str)` (function)
- L276 `refresh(record)` (function) — Read every AliExpress order of ``record``: payment state, deadline, tracking.
- L300 `sync_open_orders()` (function)
- L315 `cancel(record)` (function) — No cancel method exists: flag the order for a cancel in the AliExpress account.
