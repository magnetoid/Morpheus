---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:49'
updated: '2026-10-23T04:51:49'
rules: []
---

# plugins/installed/admin_dashboard/templatetags/morph_dashboard.py

Symbols in `plugins/installed/admin_dashboard/templatetags/morph_dashboard.py`.

- L25 `sparkline(series, width: int=120, height: int=28, stroke: str='')` (function) — Render an inline-SVG sparkline.
- L63 `sort_link(context, field, label)` (function) — Render a sortable column header.
- L109 `index_tabs(context, param, choices, counts=None)` (function) — Render an underlined tab strip for an index page status filter.
- L161 `order_row_actions(context, order)` (function) — Per-row overflow menu for an Order. Reuses `orders_bulk` for
- L199 `product_row_actions(context, product)` (function) — Per-row actions for a Product — Edit / Archive(or Restore) / Delete
- L238 `customer_row_actions(context, customer)` (function) — Per-row overflow menu for a Customer/contact row.
- L270 `dashboard_card_list(context, section)` (function) — The cards for a section's landing page (admin_dashboard/cards.py),
- L283 `get_ai_page_help()` (function)
- L299 `dashboard_page_help(context)` (function) — The current page's Help link, ``{'url', 'label', 'title'}``, or None.
- L327 `filter_chips(context, **labels)` (function) — Render chips for any request.GET param that has a non-empty value.
- L364 `event_label(value)` (function) — An order event code as words: ORDER_PAYMENT_RECEIVED -> "Payment received".
- L374 `badge_count(value)` (function) — A nav badge number, capped: 1145 unread reads as "99+", not a wall of digits.
