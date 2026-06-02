---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:52'
updated: '2026-06-02T18:07:52'
---

# plugins/installed/dynamic_products/tests/test_dynamic_products.py

Symbols in `plugins/installed/dynamic_products/tests/test_dynamic_products.py`.

- L20 `_product(slug, *, category=None, featured=False, tags=None)` (function)
- L35 `_paid_order(customer, products, *, status='confirmed')` (function)
- L62 `DynamicProductsIndexBoundaryTests` (class) — anon blocked · non-staff blocked · staff allowed (customers.Customer).
- L66 `setUpTestData(cls)` (method)
- L75 `test_anonymous_redirected_to_login(self)` (method)
- L80 `test_authed_without_scope_blocked(self)` (method)
- L86 `test_authed_staff_allowed(self)` (method)
- L97 `DynamicProductsEngineTests` (class)
- L98 `setUp(self)` (method)
- L103 `_request(self, *, user=None, session=None)` (method)
- L109 `test_manual_filters_by_category(self)` (method)
- L118 `test_manual_filters_by_tag(self)` (method)
- L127 `test_recently_viewed_reads_session(self)` (method)
- L138 `test_related_uses_same_category(self)` (method)
- L148 `test_bought_together_from_orders(self)` (method)
- L161 `test_pdp_only_strategy_empty_without_context(self)` (method)
- L169 `test_for_you_excludes_purchased(self)` (method)
- L183 `test_for_you_anonymous_fallback_not_empty(self)` (method)
- L192 `test_limit_is_respected(self)` (method)
- L201 `test_recommend_never_raises(self)` (method)
- L209 `_Anon` (class) — Minimal AnonymousUser stand-in for the engine's is_authenticated check.
