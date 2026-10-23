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

# plugins/installed/cjdropshipping/services/orders.py

Symbols in `plugins/installed/cjdropshipping/services/orders.py`.

- L41 `_bool(key: str, default: bool)` (function)
- L46 `_money(value)` (function)
- L53 `_country_code(raw)` (function)
- L64 `lines_for(order)` (function) — CJ lines for the order's shippable items, and the names of unlinked ones.
- L91 `orders_to_send()` (function) — Paid, unsent orders with at least one line linked to CJ.
- L98 `_payload(order, lines: list[dict], logistic: str, pay: bool)` (function)
- L128 `_logistic(lines: list[dict], country_code: str, zip_code: str)` (function)
- L140 `_claim(order)` (function) — Lock the order's CJOrder row for a send; ``None`` when it is already handled.
- L155 `_fail(record, message: str)` (function)
- L162 `forward_order(order, *, pay: bool | None=None)` (function) — Create ``order`` in CJ (idempotent). Returns the CJOrder, or None if already sent.
- L200 `adopt(record)` (function) — CJ already holds an order with our number: take its id and state.
- L212 `_mark_processing(order)` (function)
- L224 `pay(record)` (function) — Pay a created order from the CJ balance; returns '' or the reason it failed.
- L242 `_tracking_url(tracking: str, given: str='')` (function)
- L250 `ship(record, tracking: str, *, carrier: str='', url: str='')` (function) — Ship the store order with CJ's tracking number, once.
- L269 `_apply_detail(record, detail: dict)` (function)
- L288 `sync_open_orders()` (function) — Refresh every open CJ order from CJ (status, payment, tracking). Returns the count read.
- L312 `cancel(record)` (function) — The store order was cancelled: delete it at CJ while CJ still allows that.
