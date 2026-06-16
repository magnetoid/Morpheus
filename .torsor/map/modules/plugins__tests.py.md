---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/tests.py

Symbols in `plugins/tests.py`.

- L16 `PluginMetadataValidationTests` (class)
- L17 `test_valid_plugin_subclass(self)` (method)
- L25 `test_invalid_name_camel_case(self)` (method)
- L33 `test_missing_label(self)` (method)
- L41 `test_invalid_version(self)` (method)
- L49 `test_requires_must_be_list_of_strings(self)` (method)
- L58 `test_register_hook_validates_handler(self)` (method)
- L67 `test_register_urls_outside_ready_raises(self)` (method)
- L77 `MorphCreatePluginTests` (class)
- L78 `setUp(self)` (method)
- L81 `tearDown(self)` (method)
- L84 `_scaffold(self, name: str, **flags)` (method)
- L93 `test_scaffold_minimal(self)` (method)
- L102 `test_scaffold_with_models(self)` (method)
- L107 `test_scaffold_with_graphql_urls_tasks(self)` (method)
- L119 `test_scaffold_rejects_bad_name(self)` (method)
- L127 `test_plugin_py_compiles(self)` (method)
- L139 `PluginContributionTests` (class) — Verify plugin contribution surfaces flow through the registry.
- L142 `test_plugin_can_contribute_storefront_block(self)` (method)
- L162 `test_plugin_can_contribute_dashboard_page(self)` (method)
- L181 `test_plugin_can_contribute_settings_panel(self)` (method)
- L205 `test_drop_contributions_removes_them(self)` (method)
- L224 `StorefrontBlocksTagTests` (class) — The {% storefront_blocks 'slot' %} tag renders contributed templates.
- L227 `test_tag_renders_nothing_when_no_blocks(self)` (method)
