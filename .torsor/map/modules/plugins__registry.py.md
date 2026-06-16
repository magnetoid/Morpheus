---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:58'
updated: '2026-06-13T00:49:58'
---

# plugins/registry.py

Symbols in `plugins/registry.py`.

- L16 `PluginRegistry` (class) — Central registry for all Morph plugins.
- L29 `__init__(self)` (method)
- L51 `discover(self, plugin_module_paths: list[str])` (method)
- L63 `_find_plugin_class(self, module, module_path: str)` (method)
- L78 `validate(self)` (method)
- L95 `_topo_sort(self, names: list[str])` (method) — Topologically order plugin names by `requires` (Kahn's algorithm).
- L127 `activate_all(self)` (method)
- L164 `_activate(self, plugin: MorpheusPlugin)` (method)
- L178 `deactivate(self, name: str)` (method)
- L186 `activate(self, name: str)` (method) — Enable a plugin at runtime — the mirror of `deactivate()`.
- L223 `_refresh_urlconf(self)` (method) — Re-mount plugin URLs into the live URLconf after a runtime enable.
- L245 `_collect_contributions(self, plugin: MorpheusPlugin)` (method) — Pull `contribute_*` results from a plugin and merge them into
- L294 `_drop_contributions(self, plugin_name: str)` (method)
- L305 `storefront_blocks_for(self, slot: str)` (method)
- L308 `dashboard_pages(self, section: str | None=None)` (method)
- L313 `settings_panel(self, plugin_name: str)` (method)
- L316 `all_settings_panels(self)` (method) — Sorted list of (plugin_name, SettingsPanel) tuples — template-safe.
- L323 `_get_enabled_from_db(self)` (method)
- L355 `_update_db_status(self, name: str, enabled: bool)` (method)
- L370 `add_graphql_extension(self, module: str)` (method)
- L374 `add_plugin_urls(self, urlconf: str, prefix: str='', namespace: str='')` (method)
- L377 `add_task_module(self, module: str)` (method)
- L381 `add_context_processor(self, func)` (method)
- L386 `get_graphql_extensions(self, extension_type: str)` (method)
- L403 `get_urlpatterns(self)` (method)
- L421 `get(self, name: str)` (method)
- L424 `is_active(self, name: str)` (method)
- L427 `all_plugins(self)` (method)
- L430 `active_plugins(self)` (method)
- L433 `__repr__(self)` (method)
