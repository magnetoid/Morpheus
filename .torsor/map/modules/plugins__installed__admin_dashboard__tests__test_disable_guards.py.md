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
- L109 `HotEnableTests` (class) — registry.activate() lights a plugin up at runtime — the mirror of
- L117 `setUp(self)` (method)
- L121 `test_reenable_restores_contributions_without_restart(self)` (method)
- L137 `test_activate_is_idempotent_no_duplicate_panels(self)` (method)
- L144 `test_activate_unknown_plugin_returns_false(self)` (method)
- L148 `ProductShellContributionGuards` (class) — The products list/form shell must carry NO direct bookvault reference —
- L172 `test_products_shell_free_of_bookvault(self)` (method)
- L180 `ProtectedAppGuardTests` (class) — One source of truth for "this app may not be disabled".
- L191 `test_no_surface_can_disable_a_soft_bricking_app(self)` (method)
- L209 `test_an_app_can_protect_itself_via_its_manifest(self)` (method) — The floor is a minimum, not the whole list — a manifest can add.
- L228 `test_system_apps_are_hidden_from_the_catalogue(self)` (method)
