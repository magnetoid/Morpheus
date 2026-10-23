---
type: map
status: derived
tags:
- map
links: []
created: '2026-10-23T04:51:52'
updated: '2026-10-23T04:51:52'
rules: []
---

# plugins/registry.py

Symbols in `plugins/registry.py`.

- L16 `AppRegistry` (class) — Central registry for all Morph plugins.
- L33 `__init__(self)` (method)
- L72 `discover(self, plugin_module_paths: list[str])` (method)
- L84 `_find_plugin_class(self, module, module_path: str)` (method)
- L99 `validate(self)` (method)
- L125 `_topo_sort(self, names: list[str])` (method) — Topologically order plugin names by `requires` (Kahn's algorithm).
- L157 `activate_all(self)` (method)
- L194 `_activate(self, plugin: MorpheusPlugin)` (method)
- L208 `deactivate(self, name: str)` (method)
- L221 `activate(self, name: str)` (method) — Enable a plugin at runtime — the mirror of `deactivate()`.
- L274 `_refresh_urlconf(self)` (method) — Re-mount plugin URLs into the live URLconf after a runtime toggle.
- L306 `_collect_list(self, plugin: MorpheusPlugin, method: str, index: list)` (method) — Append one `contribute_*` list to its index, owner-tagged. A plugin
- L316 `_collect_contributions(self, plugin: MorpheusPlugin)` (method) — Pull `contribute_*` results from a plugin and merge them into
- L357 `_drop_contributions(self, plugin_name: str)` (method)
- L376 `storefront_blocks_for(self, slot: str)` (method)
- L379 `dashboard_pages(self, section: str | None=None)` (method)
- L384 `dashboard_url_mounts(self)` (method) — ``(app, '/dashboard/<prefix>/')`` for every active app that mounts
- L399 `url_prefixes(self, name: str)` (method) — The URL prefixes an app mounts its own routes under ('/' for the root).
- L407 `dashboard_cards(self, section: str | None=None)` (method) — Contributed `DashboardCard`s, sorted by section then order. Raw
- L414 `email_templates(self)` (method) — Every active plugin's contributed email templates (EmailTemplateDef),
- L419 `settings_panel(self, plugin_name: str)` (method)
- L422 `all_settings_panels(self)` (method) — Sorted list of (plugin_name, SettingsPanel) tuples — template-safe.
- L429 `_get_enabled_from_db(self)` (method)
- L473 `_update_db_status(self, name: str, enabled: bool)` (method)
- L488 `add_graphql_extension(self, module: str)` (method)
- L492 `add_plugin_urls(self, urlconf: str, prefix: str='', namespace: str='', plugin: str='', surface: str | None=None)` (method) — Record a plugin URLconf mount.
- L523 `add_task_module(self, module: str)` (method)
- L527 `add_context_processor(self, func, plugin: str | None=None)` (method) — Record a plugin-contributed context processor as (func, owner). The
- L534 `context_processors(self)` (method) — The (func, owner) context processors plugins contributed via
- L543 `get_graphql_extensions(self, extension_type: str)` (method)
- L560 `get_urlpatterns(self, *, storefront: bool | None=None)` (method) — Build plugin URL patterns.
- L626 `get(self, name: str)` (method)
- L629 `config_value(self, name: str, key: str, default=None)` (method) — One plugin's config value, fail-soft.
- L644 `is_active(self, name: str)` (method)
- L647 `all_plugins(self)` (method)
- L650 `active_plugins(self)` (method)
- L653 `__repr__(self)` (method)
