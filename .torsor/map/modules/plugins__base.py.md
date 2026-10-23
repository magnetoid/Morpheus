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

# plugins/base.py

Symbols in `plugins/base.py`.

- L34 `PluginConfigurationError` (class) — Raised when a plugin's metadata is invalid at class-definition time.
- L38 `MorpheusPlugin` (class) — Base class for all Morpheus plugins.
- L122 `__init_subclass__(cls, **kwargs: Any)` (method)
- L130 `_validate_metadata(cls)` (method)
- L159 `ready(self)` (method) — Hook your registrations here. Called once per process boot.
- L162 `on_disable(self)` (method) — Tear-down hook. Called when a merchant disables the plugin.
- L167 `register_urls(self, urlconf: str, prefix: str='', namespace: str | None=None, surface: str | None=None)` (method) — Mount a URLconf module under `prefix` with the given `namespace`.
- L197 `register_graphql_extension(self, module: str)` (method) — Register a Strawberry mixin module (`<X>QueryExtension`/`<X>MutationExtension`).
- L205 `register_hook(self, event: str, handler: Callable, priority: int=50)` (method) — Subscribe a callable to a domain event. Lower priority runs first.
- L219 `register_admin(self, model: Any, admin_class: Any)` (method) — Register a Django admin entry. Idempotent; ignores AlreadyRegistered.
- L228 `register_celery_tasks(self, module: str)` (method) — Make Celery aware of a tasks module from this plugin.
- L234 `register_context_processor(self, func: Callable)` (method) — Contribute a template context processor that runs on every request.
- L250 `register_celery_beat(self, name: str, entry: dict)` (method) — Add a Celery beat schedule entry. Existing entries are not overwritten.
- L261 `get_config_schema(self)` (method) — JSON Schema for this plugin's settings (rendered as a form in admin).
- L265 `get_config(self)` (method) — Read current config from DB (cached).
- L287 `get_config_value(self, key: str, default: Any=None)` (method) — Get one config value with fallback to schema default.
- L295 `set_config(self, key: str, value: Any)` (method) — Persist one config value (and invalidate the cache).
- L304 `invalidate_config_cache(self)` (method)
- L313 `contribute_storefront_blocks(self)` (method) — Return a list of `StorefrontBlock` instances.
- L322 `contribute_dashboard_pages(self)` (method) — Return a list of `DashboardPage` entries.
- L331 `contribute_dashboard_cards(self)` (method) — Return a list of `DashboardCard` widgets.
- L340 `contribute_settings_panel(self)` (method) — Return a `SettingsPanel` (or `None`).
- L348 `contribute_email_templates(self)` (method) — Return a list of `EmailTemplateDef` — this plugin's transactional
- L357 `contribute_agents(self)` (method) — Return a list of `MorpheusAgent` instances this plugin ships.
- L366 `contribute_agent_tools(self)` (method) — Return a list of `core.agents.Tool` instances this plugin exposes.
- L376 `contribute_skills(self)` (method) — Return a list of `core.agents.Skill` bundles this plugin exposes.
- L389 `__repr__(self)` (method)
