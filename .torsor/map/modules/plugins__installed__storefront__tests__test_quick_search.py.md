---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/installed/storefront/tests/test_quick_search.py

Symbols in `plugins/installed/storefront/tests/test_quick_search.py`.

- L19 `QuickSearchTests` (class)
- L20 `setUp(self)` (method)
- L42 `_fetch(self, q)` (method)
- L45 `test_empty_query_returns_empty_results(self)` (method)
- L50 `test_single_char_returns_empty_results(self)` (method) — Without the 2-char floor the topbar would 500-cascade the
- L57 `test_response_shape_is_stable(self)` (method)
- L65 `test_draft_products_excluded(self)` (method) — status='draft' must never leak via quick-search — it's the
- L73 `test_each_result_has_required_keys(self)` (method) — Stable shape — every row needs id/name/slug/price/image_url.
