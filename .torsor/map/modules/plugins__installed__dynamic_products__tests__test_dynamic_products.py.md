---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:49'
updated: '2026-06-10T20:08:49'
---

# plugins/installed/dynamic_products/tests/test_dynamic_products.py

Symbols in `plugins/installed/dynamic_products/tests/test_dynamic_products.py`.

- L22 `_product(slug, *, category=None, featured=False, tags=None)` (function)
- L37 `_paid_order(customer, products, *, status='confirmed')` (function)
- L64 `DynamicProductsIndexBoundaryTests` (class) — anon blocked · non-staff blocked · staff allowed (customers.Customer).
- L68 `setUpTestData(cls)` (method)
- L77 `test_anonymous_redirected_to_login(self)` (method)
- L82 `test_authed_without_scope_blocked(self)` (method)
- L88 `test_authed_staff_allowed(self)` (method)
- L99 `DynamicProductsEngineTests` (class)
- L100 `setUp(self)` (method)
- L105 `_request(self, *, user=None, session=None)` (method)
- L111 `test_manual_filters_by_category(self)` (method)
- L124 `test_manual_filters_by_tag(self)` (method)
- L133 `test_recently_viewed_reads_session(self)` (method)
- L144 `test_related_uses_same_category(self)` (method)
- L154 `test_bought_together_from_orders(self)` (method)
- L167 `test_pdp_only_strategy_empty_without_context(self)` (method)
- L175 `test_for_you_excludes_purchased(self)` (method)
- L189 `test_for_you_anonymous_fallback_not_empty(self)` (method)
- L198 `test_limit_is_respected(self)` (method)
- L207 `test_recommend_never_raises(self)` (method)
- L215 `_Anon` (class) — Minimal AnonymousUser stand-in for the engine's is_authenticated check.
