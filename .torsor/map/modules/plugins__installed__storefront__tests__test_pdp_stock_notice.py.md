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

# plugins/installed/storefront/tests/test_pdp_stock_notice.py

Symbols in `plugins/installed/storefront/tests/test_pdp_stock_notice.py`.

- L27 `PdpStockNoticeTests` (class)
- L29 `setUpTestData(cls)` (method)
- L32 `_product(self, slug, **kwargs)` (method)
- L42 `_variant(self, product, *, stock=None, reserved=0, policy='deny')` (method)
- L55 `_shows_notice(self, product)` (method)
- L60 `test_a_product_without_variants_is_not_out_of_stock(self)` (method)
- L63 `test_a_variant_without_stock_rows_is_untracked_not_empty(self)` (method)
- L68 `test_a_backorder_variant_is_still_buyable(self)` (method)
- L73 `test_a_sold_out_variant_shows_the_notice(self)` (method)
- L78 `test_fully_reserved_stock_is_sold_out(self)` (method)
- L83 `test_stock_on_hand_hides_the_notice(self)` (method)
