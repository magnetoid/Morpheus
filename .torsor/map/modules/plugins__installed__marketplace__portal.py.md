---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:51'
updated: '2026-10-23T04:51:51'
rules: []
---

# plugins/installed/marketplace/portal.py

Symbols in `plugins/installed/marketplace/portal.py`.

- L55 `vendor_noun()` (function) — ``(singular, plural)``: what this store calls its vendors, from the theme
- L66 `resolve(user)` (function) — ``(vendor, application)`` for ``user``: the vendor they own (an active one
- L78 `status_of(vendor, application)` (function)
- L99 `sold_orders(vendor)` (function)
- L107 `open_orders(vendor)` (function) — Slices still to be sent, oldest first.
- L119 `payment_state(order)` (function) — paid · cod (paid to the courier on delivery, so ship it) · awaiting.
- L128 `display_state(vendor_order)` (function) — The slice's status as the vendor should read it: a store-cancelled order
- L136 `decorate(vendor_orders)` (function) — Attach what a row needs: payment state, display state, item count, ship-to.
- L158 `_int(value)` (function)
- L168 `_amount(value)` (function)
- L172 `_sum(qs, field: str)` (function)
- L176 `currency_of(vendor)` (function)
- L191 `money_text(value)` (function)
- L197 `payout_threshold()` (function)
- L208 `balance(vendor, account)` (function) — The vendor's balance with the store and whether a payout can be asked for.
- L252 `_daily(qs, value)` (function)
- L258 `performance(vendor, period: pp.Period)` (function) — KPI tiles and the sales chart for ``period``.
- L323 `units_by_sku(vendor, since=None)` (function) — ``{sku or name: {'name', 'sku', 'units', 'revenue'}}`` from the order snapshots.
- L356 `best_sellers(vendor, period: pp.Period, limit: int=5)` (function)
- L379 `stock_for(product_ids)` (function) — The inventory app's stock answer, or ``{}`` when nothing answers.
- L390 `image_url(product)` (function)
- L404 `decorate_products(vendor, products)` (function) — Attach stock, units sold in the last 30 days and a thumbnail to each product.
- L420 `stock_status(vendor)` (function) — ``{'attention': [...], 'tracked': n}`` — the vendor's live products that
- L440 `attention_products(vendor)` (function)
- L447 `nav(vendor)` (function)
- L459 `shell(user, vendor, application, *, active: str, title: str)` (function) — The portal context for one of the vendor's pages.
- L492 `_public_page(vendor)` (function)
- L501 `_logo_url(vendor)` (function)
