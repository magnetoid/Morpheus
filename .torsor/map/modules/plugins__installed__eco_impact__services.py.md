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

# plugins/installed/eco_impact/services.py

Symbols in `plugins/installed/eco_impact/services.py`.

- L28 `_cfg(key, default)` (function)
- L35 `show_on_pdp()` (function)
- L39 `surcharge_amount()` (function) — The flat plant-a-tree opt-in price, as a quantised Decimal.
- L47 `kg_co2_per_tree()` (function)
- L54 `factors_from_settings()` (function) — Merchant-tuned overrides for the footprint calculator (only set keys).
- L68 `_book_for(product_id)` (function)
- L74 `impact_for_product(product)` (function) — Production-footprint dict for a PDP ``product`` (GraphQL dict OR ORM),
- L112 `_current_cart(request)` (function) — The visitor's cart (auth → by customer, guest → by session_key), or None.
- L132 `optin_active(request)` (function)
- L139 `set_optin(request, on: bool)` (function)
- L155 `record_pledge(order, trees: int, amount, currency: str='USD')` (function) — Idempotently record a tree pledge for a paid order. Returns the new row,
- L177 `remove_pledge(order)` (function) — Void a pledge when its order is cancelled, so store totals stay honest.
- L184 `store_totals()` (function) — Aggregate impact for the storefront + dashboard summaries.
