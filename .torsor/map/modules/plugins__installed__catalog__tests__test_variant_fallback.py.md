---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/catalog/tests/test_variant_fallback.py

Symbols in `plugins/installed/catalog/tests/test_variant_fallback.py`.

- L26 `_make_product(**overrides)` (function)
- L43 `_make_variant(product, **overrides)` (function)
- L56 `DisplayPriceTests` (class)
- L57 `test_simple_product_returns_own_price(self)` (method)
- L62 `test_variable_returns_min_variant_price(self)` (method)
- L76 `test_variable_single_variant_no_from_prefix(self)` (method)
- L88 `test_variable_inactive_variants_excluded(self)` (method)
- L103 `VariantCopyFallbackTests` (class) — The GraphQL ProductVariantType.short_description / description
- L110 `_get_resolver(self, attr)` (method)
- L126 `test_short_description_falls_back_to_parent(self)` (method)
- L139 `test_description_keeps_variant_value_when_set(self)` (method)
- L148 `VariantSalePriceTests` (class) — GraphQL ProductVariantType exposes compare_at_price / is_on_sale /
- L154 `_get_resolver(self, attr)` (method)
- L164 `test_is_on_sale_when_variant_has_compare_above_price(self)` (method)
- L178 `test_no_sale_when_compare_below_price(self)` (method)
- L191 `test_compare_at_falls_back_to_parent_product(self)` (method)
- L207 `test_no_compare_means_no_sale(self)` (method)
- L214 `FlipbookViewTests` (class)
- L215 `test_404_when_product_missing(self)` (method)
- L221 `test_404_when_product_has_no_pdf(self)` (method)
