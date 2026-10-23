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

# plugins/installed/zendrop/services/orders.py

Symbols in `plugins/installed/zendrop/services/orders.py`.

- L32 `_config()` (function)
- L39 `awaiting_orders()` (function) — Paid, shippable orders not yet placed in Zendrop.
- L44 `order_sheet(order)` (function) — Everything the merchant types into Zendrop for this order, ready to copy.
- L74 `mark_placed(order, zendrop_order_number: str='')` (function) — Record that the order was placed in Zendrop; move it to processing if configured.
- L92 `ship_order(order, tracking: str, carrier: str='', zendrop_order_number: str='')` (function) — Ship one order with ``tracking``. Returns '' on success, else the reason it was skipped.
- L117 `import_tracking(text: str)` (function) — Ship every order a tracking CSV names. Returns shipped / skipped / unknown.
