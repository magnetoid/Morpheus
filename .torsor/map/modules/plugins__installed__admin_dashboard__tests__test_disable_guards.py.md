---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/installed/admin_dashboard/tests/test_disable_guards.py

Symbols in `plugins/installed/admin_dashboard/tests/test_disable_guards.py`.

- L29 `PluginEnabledTagTests` (class)
- L30 `_render(self, slug: str)` (method)
- L37 `test_active_plugin_is_true(self)` (method)
- L41 `test_disabled_plugin_is_false(self)` (method)
- L50 `test_unknown_plugin_is_false(self)` (method)
- L54 `DashboardNavGuardTests` (class) — Each hardcoded, plugin-owned nav href must be on a line that also carries
- L65 `test_plugin_nav_links_are_guarded(self)` (method)
- L79 `test_contributed_nav_is_not_hardcoded(self)` (method)
- L102 `HotEnableTests` (class) — registry.activate() lights a plugin up at runtime — the mirror of
- L110 `setUp(self)` (method)
- L114 `test_reenable_restores_contributions_without_restart(self)` (method)
- L130 `test_activate_is_idempotent_no_duplicate_panels(self)` (method)
- L137 `test_activate_unknown_plugin_returns_false(self)` (method)
