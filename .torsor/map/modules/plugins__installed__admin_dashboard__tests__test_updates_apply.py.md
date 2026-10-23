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

# plugins/installed/admin_dashboard/tests/test_updates_apply.py

Symbols in `plugins/installed/admin_dashboard/tests/test_updates_apply.py`.

- L13 `_pin_standalone_updater(test)` (function) — `/dashboard/updates/` is the disable-safe standalone updater; when the
- L25 `UpdatesApplyTests` (class)
- L26 `setUp(self)` (method)
- L34 `test_get_does_not_apply(self)` (method)
- L40 `test_post_calls_guarded_updater(self)` (method)
- L49 `test_disabled_is_reported_not_fatal(self)` (method)
- L57 `test_page_renders(self)` (method)
- L63 `ComponentUpdatesSurfaceTests` (class) — The per-app / per-theme channel on the Updates page.
- L78 `setUp(self)` (method)
- L93 `_cache(self, components)` (method)
- L102 `test_page_lists_cached_component_updates_with_an_apply_button(self)` (method)
- L109 `test_core_blocked_component_shows_no_apply_button(self)` (method)
- L115 `test_page_without_component_updates_says_so(self)` (method)
- L119 `test_get_apply_does_not_apply(self)` (method)
- L125 `test_post_apply_calls_the_guarded_engine_with_confirm(self)` (method)
- L134 `test_check_refreshes_the_cache_so_components_appear(self)` (method) — The Check button must populate the same cache the page reads —
- L145 `StandaloneUpdaterBuiltImageTests` (class) — The standalone /dashboard/updates/ page tells the same truth (safe deploys, part 5).
- L148 `setUp(self)` (method)
- L155 `test_a_built_image_gets_one_line_instead_of_buttons(self)` (method)
