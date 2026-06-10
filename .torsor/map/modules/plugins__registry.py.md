---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-10T20:08:51'
updated: '2026-06-10T20:08:51'
---

# plugins/registry.py

Symbols in `plugins/registry.py`.

- L17 `PluginRegistry` (class) — Central registry for all Morph plugins.
- L30 `__init__(self)` (method)
- L52 `discover(self, plugin_module_paths: list[str])` (method)
- L64 `_find_plugin_class(self, module, module_path: str)` (method)
- L79 `validate(self)` (method)
- L96 `_topo_sort(self, names: list[str])` (method) — Topologically order plugin names by `requires` (Kahn's algorithm).
- L128 `activate_all(self)` (method)
- L165 `_activate(self, plugin: MorpheusPlugin)` (method)
- L179 `deactivate(self, name: str)` (method)
- L187 `activate(self, name: str)` (method) — Enable a plugin at runtime — the mirror of `deactivate()`.
- L224 `_refresh_urlconf(self)` (method) — Re-mount plugin URLs into the live URLconf after a runtime enable.
- L246 `_collect_contributions(self, plugin: MorpheusPlugin)` (method) — Pull `contribute_*` results from a plugin and merge them into
- L295 `_drop_contributions(self, plugin_name: str)` (method)
- L306 `storefront_blocks_for(self, slot: str)` (method)
- L309 `dashboard_pages(self, section: str | None=None)` (method)
- L314 `settings_panel(self, plugin_name: str)` (method)
- L317 `all_settings_panels(self)` (method) — Sorted list of (plugin_name, SettingsPanel) tuples — template-safe.
- L324 `_get_enabled_from_db(self)` (method)
- L356 `_update_db_status(self, name: str, enabled: bool)` (method)
- L371 `add_graphql_extension(self, module: str)` (method)
- L375 `add_plugin_urls(self, urlconf: str, prefix: str='', namespace: str='')` (method)
- L378 `add_task_module(self, module: str)` (method)
- L382 `add_context_processor(self, func)` (method)
- L387 `get_graphql_extensions(self, extension_type: str)` (method)
- L404 `get_urlpatterns(self)` (method)
- L422 `get(self, name: str)` (method)
- L425 `is_active(self, name: str)` (method)
- L428 `all_plugins(self)` (method)
- L431 `active_plugins(self)` (method)
- L434 `__repr__(self)` (method)
