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

# core/tests/test_price_filter.py

Symbols in `core/tests/test_price_filter.py`.

- L24 `_usd(n)` (function)
- L28 `_Sub` (class) — Temporarily subscribe a pricing handler for the duration of a test.
- L31 `__init__(self, fn)` (method)
- L34 `__enter__(self)` (method)
- L38 `__exit__(self, *exc)` (method)
- L42 `PriceFilterGuardTests` (class)
- L43 `test_handler_adjusts_price(self)` (method)
- L47 `test_no_subscriber_is_a_passthrough(self)` (method)
- L50 `test_broken_handler_keeps_the_original_price(self)` (method)
- L57 `test_non_money_return_is_ignored(self)` (method)
- L63 `test_negative_price_is_ignored(self)` (method)
- L67 `test_currency_swap_is_ignored(self)` (method)
- L75 `DisplayMatchesChargeTests` (class) — The seam fires on BOTH the displayed and the charged price.
- L78 `setUp(self)` (method)
- L85 `test_cart_add_uses_the_adjusted_price(self)` (method)
- L93 `test_displayed_price_uses_the_adjusted_price(self)` (method)
- L104 `ListingMatchesPdpTests` (class) — The shelf must quote the same price as the PDP and the cart.
- L114 `setUp(self)` (method)
- L121 `_card_price(self)` (method)
- L127 `test_card_price_uses_the_seam(self)` (method)
- L131 `test_the_real_product_card_template_uses_the_seam(self)` (method) — Render the actual card, not a stand-in.
- L145 `test_card_price_unfiltered_without_a_rule(self)` (method)
- L148 `test_home_serialisation_uses_the_seam(self)` (method)
- L154 `test_graphql_dict_is_not_double_filtered(self)` (method)
