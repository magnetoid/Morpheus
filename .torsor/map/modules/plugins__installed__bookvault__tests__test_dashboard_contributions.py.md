---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:50'
updated: '2026-10-23T04:51:50'
rules: []
---

# plugins/installed/bookvault/tests/test_dashboard_contributions.py

Symbols in `plugins/installed/bookvault/tests/test_dashboard_contributions.py`.

- L25 `_product(slug: str)` (function)
- L35 `ListColumnContributionTests` (class)
- L36 `_columns(self, products)` (method) — Bookvault's OWN contributions to the shared accumulator.
- L48 `test_unauthed_contributes_nothing(self)` (method)
- L51 `test_authed_contributes_column_and_annotates_products(self)` (method)
- L64 `test_disabled_plugin_contributes_nothing(self)` (method)
- L75 `FormCardContributionTests` (class)
- L76 `_bv_cards(self, product)` (method)
- L80 `test_no_product_or_unauthed_contributes_nothing(self)` (method)
- L85 `test_authed_card_contributes_and_renders(self)` (method)
- L97 `ProductsPageEndToEndTests` (class) — Full round trip: subscriber → _collect_product_list_columns →
- L103 `setUp(self)` (method)
- L109 `test_column_and_bulk_action_render_when_authed(self)` (method)
- L119 `test_everything_vanishes_when_disabled(self)` (method)
