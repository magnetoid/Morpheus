---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-02T18:07:53'
updated: '2026-06-02T18:07:53'
---

# plugins/registry.py

Symbols in `plugins/registry.py`.

- L16 `PluginRegistry` (class) — Central registry for all Morph plugins.
- L29 `__init__(self)` (method)
- L47 `discover(self, plugin_module_paths: list[str])` (method)
- L59 `_find_plugin_class(self, module, module_path: str)` (method)
- L74 `validate(self)` (method)
- L91 `_topo_sort(self, names: list[str])` (method) — Topologically order plugin names by `requires` (Kahn's algorithm).
- L123 `activate_all(self)` (method)
- L159 `_activate(self, plugin: MorpheusPlugin)` (method)
- L172 `deactivate(self, name: str)` (method)
- L182 `_collect_contributions(self, plugin: MorpheusPlugin)` (method) — Pull `contribute_*` results from a plugin and merge them into
- L222 `_drop_contributions(self, plugin_name: str)` (method)
- L232 `storefront_blocks_for(self, slot: str)` (method)
- L235 `dashboard_pages(self, section: str | None=None)` (method)
- L240 `settings_panel(self, plugin_name: str)` (method)
- L243 `all_settings_panels(self)` (method) — Sorted list of (plugin_name, SettingsPanel) tuples — template-safe.
- L250 `_get_enabled_from_db(self)` (method)
- L281 `_update_db_status(self, name: str, enabled: bool)` (method)
- L293 `add_graphql_extension(self, module: str)` (method)
- L297 `add_plugin_urls(self, urlconf: str, prefix: str='', namespace: str='')` (method)
- L300 `add_task_module(self, module: str)` (method)
- L304 `add_context_processor(self, func)` (method)
- L309 `get_graphql_extensions(self, extension_type: str)` (method)
- L326 `get_urlpatterns(self)` (method)
- L343 `get(self, name: str)` (method)
- L346 `is_active(self, name: str)` (method)
- L349 `all_plugins(self)` (method)
- L352 `active_plugins(self)` (method)
- L355 `__repr__(self)` (method)
