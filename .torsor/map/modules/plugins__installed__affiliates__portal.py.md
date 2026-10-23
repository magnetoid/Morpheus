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

# plugins/installed/affiliates/portal.py

Symbols in `plugins/installed/affiliates/portal.py`.

- L40 `nav()` (function)
- L55 `shell(affiliate, *, active: str, title: str)` (function) — The portal context for one of ``affiliate``'s pages.
- L75 `currency_of(affiliate)` (function) — The currency the affiliate is paid in: their latest commission's, else
- L89 `_amount(value)` (function)
- L93 `_sum(qs, field: str)` (function)
- L97 `money_text(value)` (function)
- L103 `count_text(value)` (function)
- L110 `balances(affiliate)` (function) — Where the affiliate's commission stands, and whether a payout can be asked for.
- L147 `_daily(qs, field: str, value=None)` (function)
- L152 `performance(affiliate, period: pp.Period)` (function) — KPI tiles, the commission chart and the funnel for ``period``.
- L236 `_average_order(conversions, currency: str)` (function) — Average total of the referred orders.
- L247 `link_stats(affiliate, links, *, since=None)` (function) — Annotate each link with its orders and commission (``since`` or lifetime)
- L271 `top_links(affiliate, period: pp.Period, limit: int=5)` (function)
- L283 `top_products(affiliate, period: pp.Period | None, limit: int=5)` (function) — What customers bought in the orders this affiliate referred.
- L316 `traffic_sources(affiliate, period: pp.Period, limit: int=8)` (function) — Where this period's clicks came from, by referring site.
- L342 `payout_state(conversion)` (function) — Where one conversion's commission is: in review, approved, in a payout, paid, reversed.
