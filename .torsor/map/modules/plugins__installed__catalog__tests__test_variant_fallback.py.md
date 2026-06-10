---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/installed/catalog/tests/test_variant_fallback.py

Symbols in `plugins/installed/catalog/tests/test_variant_fallback.py`.

- L25 `_make_product(**overrides)` (function)
- L41 `_make_variant(product, **overrides)` (function)
- L53 `DisplayPriceTests` (class)
- L54 `test_simple_product_returns_own_price(self)` (method)
- L59 `test_variable_returns_min_variant_price(self)` (method)
- L71 `test_variable_single_variant_no_from_prefix(self)` (method)
- L81 `test_variable_inactive_variants_excluded(self)` (method)
- L93 `VariantCopyFallbackTests` (class) — The GraphQL ProductVariantType.short_description / description
- L100 `_get_resolver(self, attr)` (method)
- L115 `test_short_description_falls_back_to_parent(self)` (method)
- L127 `test_description_keeps_variant_value_when_set(self)` (method)
- L136 `VariantSalePriceTests` (class) — GraphQL ProductVariantType exposes compare_at_price / is_on_sale /
- L142 `_get_resolver(self, attr)` (method)
- L151 `test_is_on_sale_when_variant_has_compare_above_price(self)` (method)
- L164 `test_no_sale_when_compare_below_price(self)` (method)
- L176 `test_compare_at_falls_back_to_parent_product(self)` (method)
- L191 `test_no_compare_means_no_sale(self)` (method)
- L198 `FlipbookViewTests` (class)
- L199 `test_404_when_product_missing(self)` (method)
- L204 `test_404_when_product_has_no_pdf(self)` (method)
