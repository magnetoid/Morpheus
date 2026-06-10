---
type: map
status: derived
tags:
- map
links: []
created: '2026-06-09T21:57:01'
updated: '2026-06-09T21:57:01'
---

# plugins/base.py

Symbols in `plugins/base.py`.

- L32 `PluginConfigurationError` (class) — Raised when a plugin's metadata is invalid at class-definition time.
- L36 `MorpheusPlugin` (class) — Base class for all Morpheus plugins.
- L101 `__init_subclass__(cls, **kwargs: Any)` (method)
- L109 `_validate_metadata(cls)` (method)
- L138 `ready(self)` (method) — Hook your registrations here. Called once per process boot.
- L141 `on_disable(self)` (method) — Tear-down hook. Called when a merchant disables the plugin.
- L146 `register_urls(self, urlconf: str, prefix: str='', namespace: str | None=None)` (method) — Mount a URLconf module under `prefix` with the given `namespace`.
- L161 `register_graphql_extension(self, module: str)` (method) — Register a Strawberry mixin module (`<X>QueryExtension`/`<X>MutationExtension`).
- L169 `register_hook(self, event: str, handler: Callable, priority: int=50)` (method) — Subscribe a callable to a domain event. Lower priority runs first.
- L180 `register_admin(self, model: Any, admin_class: Any)` (method) — Register a Django admin entry. Idempotent; ignores AlreadyRegistered.
- L188 `register_celery_tasks(self, module: str)` (method) — Make Celery aware of a tasks module from this plugin.
- L194 `register_context_processor(self, func: Callable)` (method) — Add a template context processor that runs on every request.
- L202 `register_celery_beat(self, name: str, entry: dict)` (method) — Add a Celery beat schedule entry. Existing entries are not overwritten.
- L212 `get_config_schema(self)` (method) — JSON Schema for this plugin's settings (rendered as a form in admin).
- L216 `get_config(self)` (method) — Read current config from DB (cached).
- L229 `get_config_value(self, key: str, default: Any=None)` (method) — Get one config value with fallback to schema default.
- L237 `set_config(self, key: str, value: Any)` (method) — Persist one config value (and invalidate the cache).
- L245 `invalidate_config_cache(self)` (method)
- L254 `contribute_storefront_blocks(self)` (method) — Return a list of `StorefrontBlock` instances.
- L263 `contribute_dashboard_pages(self)` (method) — Return a list of `DashboardPage` entries.
- L271 `contribute_settings_panel(self)` (method) — Return a `SettingsPanel` (or `None`).
- L279 `contribute_agents(self)` (method) — Return a list of `MorpheusAgent` instances this plugin ships.
- L288 `contribute_agent_tools(self)` (method) — Return a list of `core.agents.Tool` instances this plugin exposes.
- L298 `contribute_skills(self)` (method) — Return a list of `core.agents.Skill` bundles this plugin exposes.
- L311 `__repr__(self)` (method)
