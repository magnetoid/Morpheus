---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/tests.py

Symbols in `plugins/tests.py`.

- L15 `PluginMetadataValidationTests` (class)
- L17 `test_valid_plugin_subclass(self)` (method)
- L24 `test_invalid_name_camel_case(self)` (method)
- L31 `test_missing_label(self)` (method)
- L38 `test_invalid_version(self)` (method)
- L45 `test_requires_must_be_list_of_strings(self)` (method)
- L53 `test_register_hook_validates_handler(self)` (method)
- L61 `test_register_urls_outside_ready_raises(self)` (method)
- L70 `MorphCreatePluginTests` (class)
- L72 `setUp(self)` (method)
- L75 `tearDown(self)` (method)
- L78 `_scaffold(self, name: str, **flags)` (method)
- L87 `test_scaffold_minimal(self)` (method)
- L96 `test_scaffold_with_models(self)` (method)
- L101 `test_scaffold_with_graphql_urls_tasks(self)` (method)
- L113 `test_scaffold_rejects_bad_name(self)` (method)
- L121 `test_plugin_py_compiles(self)` (method)
- L131 `PluginContributionTests` (class) — Verify plugin contribution surfaces flow through the registry.
- L134 `test_plugin_can_contribute_storefront_block(self)` (method)
- L154 `test_plugin_can_contribute_dashboard_page(self)` (method)
- L173 `test_plugin_can_contribute_settings_panel(self)` (method)
- L194 `test_drop_contributions_removes_them(self)` (method)
- L213 `StorefrontBlocksTagTests` (class) — The {% storefront_blocks 'slot' %} tag renders contributed templates.
- L216 `test_tag_renders_nothing_when_no_blocks(self)` (method)
