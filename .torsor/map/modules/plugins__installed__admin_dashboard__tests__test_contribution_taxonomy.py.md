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

# plugins/installed/admin_dashboard/tests/test_contribution_taxonomy.py

Symbols in `plugins/installed/admin_dashboard/tests/test_contribution_taxonomy.py`.

- L22 `TaxonomyCheckTests` (class)
- L23 `test_live_registry_is_clean(self)` (method) — Every registered plugin's panel category + page nav is valid.
- L27 `test_unknown_settings_category_is_an_error(self)` (method)
- L38 `test_old_category_slugs_are_aliased_not_errors(self)` (method)
- L51 `test_unlisted_section_is_a_warning(self)` (method)
- L69 `test_card_on_a_landing_without_cards_is_a_warning(self)` (method)
- L82 `test_unknown_nav_is_an_error(self)` (method)
- L98 `RemappedPanelsRenderTests` (class) — The 8 remapped panels must actually appear on their category pages.
- L101 `setUp(self)` (method)
- L108 `_panel_labels(self, *plugin_names)` (method) — Panel labels as they appear in rendered HTML (auto-escaped —
- L118 `test_payments_category_shows_checkout_panels(self)` (method)
- L127 `test_remaining_remaps_land_on_their_pages(self)` (method)
- L141 `test_ai_page_renders_sibling_ai_panels(self)` (method) — settings_ai used to hardcode ai_content; ai_stylist's panel was
- L150 `test_gift_cards_canonical_url_resolves(self)` (method)
