---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-13T00:49:57'
updated: '2026-06-13T00:49:57'
---

# plugins/base.py

Symbols in `plugins/base.py`.

- L34 `PluginConfigurationError` (class) — Raised when a plugin's metadata is invalid at class-definition time.
- L38 `MorpheusPlugin` (class) — Base class for all Morpheus plugins.
- L103 `__init_subclass__(cls, **kwargs: Any)` (method)
- L111 `_validate_metadata(cls)` (method)
- L140 `ready(self)` (method) — Hook your registrations here. Called once per process boot.
- L143 `on_disable(self)` (method) — Tear-down hook. Called when a merchant disables the plugin.
- L148 `register_urls(self, urlconf: str, prefix: str='', namespace: str | None=None)` (method) — Mount a URLconf module under `prefix` with the given `namespace`.
- L167 `register_graphql_extension(self, module: str)` (method) — Register a Strawberry mixin module (`<X>QueryExtension`/`<X>MutationExtension`).
- L175 `register_hook(self, event: str, handler: Callable, priority: int=50)` (method) — Subscribe a callable to a domain event. Lower priority runs first.
- L187 `register_admin(self, model: Any, admin_class: Any)` (method) — Register a Django admin entry. Idempotent; ignores AlreadyRegistered.
- L196 `register_celery_tasks(self, module: str)` (method) — Make Celery aware of a tasks module from this plugin.
- L202 `register_context_processor(self, func: Callable)` (method) — Add a template context processor that runs on every request.
- L210 `register_celery_beat(self, name: str, entry: dict)` (method) — Add a Celery beat schedule entry. Existing entries are not overwritten.
- L221 `get_config_schema(self)` (method) — JSON Schema for this plugin's settings (rendered as a form in admin).
- L225 `get_config(self)` (method) — Read current config from DB (cached).
- L239 `get_config_value(self, key: str, default: Any=None)` (method) — Get one config value with fallback to schema default.
- L247 `set_config(self, key: str, value: Any)` (method) — Persist one config value (and invalidate the cache).
- L256 `invalidate_config_cache(self)` (method)
- L265 `contribute_storefront_blocks(self)` (method) — Return a list of `StorefrontBlock` instances.
- L274 `contribute_dashboard_pages(self)` (method) — Return a list of `DashboardPage` entries.
- L282 `contribute_settings_panel(self)` (method) — Return a `SettingsPanel` (or `None`).
- L290 `contribute_agents(self)` (method) — Return a list of `MorpheusAgent` instances this plugin ships.
- L299 `contribute_agent_tools(self)` (method) — Return a list of `core.agents.Tool` instances this plugin exposes.
- L309 `contribute_skills(self)` (method) — Return a list of `core.agents.Skill` bundles this plugin exposes.
- L322 `__repr__(self)` (method)
