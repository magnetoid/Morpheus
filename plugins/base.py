"""
Morpheus — MorpheusPlugin base class.

Every plugin in `plugins/installed/` subclasses `MorpheusPlugin`. The base
class:

* Validates required metadata at subclass time (name, version, label).
* Provides a single, well-documented set of registration helpers
  (`register_hook`, `register_graphql_extension`, `register_urls`, …) so
  third-party plugins never reach into the registry directly.
* Defers all expensive work to `ready()`, which the registry calls in
  topologically-sorted dependency order.

For a full developer guide see `docs/PLUGIN_DEVELOPMENT.md`.
For a step-by-step skill, see `SKILLS.md` → "Add a new plugin".
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plugins.registry import PluginRegistry

logger = logging.getLogger('morpheus.plugins')

_NAME_RE = re.compile(r'^[a-z][a-z0-9_]*$')
_VERSION_RE = re.compile(r'^\d+(\.\d+)*([a-z][0-9]*)?$')


class PluginConfigurationError(TypeError):
    """Raised when a plugin's metadata is invalid at class-definition time."""


class MorpheusPlugin:
    """
    Base class for all Morpheus plugins.

    A minimal plugin looks like::

        from plugins.base import MorpheusPlugin
        from core.hooks import MorpheusEvents

        class HelloPlugin(MorpheusPlugin):
            name = "hello"
            label = "Hello World"
            version = "0.1.0"
            description = "Logs every order placed."
            has_models = False

            def ready(self) -> None:
                self.register_hook(MorpheusEvents.ORDER_PLACED, self.on_order)

            def on_order(self, order, **kwargs):
                import logging
                logging.getLogger("hello").info("New order: %s", order.id)

    Lifecycle
    ---------
    1. `discover()` imports `<plugin>/plugin.py` and locates the subclass.
    2. `validate()` checks the dependency graph (requires/conflicts) and
       topologically sorts plugins.
    3. `activate_all()` instantiates each plugin and calls `ready()` in
       dependency order. Crashing in `ready()` deactivates *that* plugin
       only — siblings keep loading.
    4. `on_disable()` is called when a merchant turns the plugin off.

    Extension points (call from `ready()`)
    --------------------------------------
    * `register_hook(event, handler, priority=50)` — subscribe to events.
    * `register_graphql_extension('module.path')` — schema mixins.
    * `register_urls('module.path', prefix='', namespace=name)` — HTTP routes.
    * `register_admin(Model, AdminCls)` — Django admin.
    * `register_celery_tasks('module.path')` — register tasks for autodiscovery.
    * `register_celery_beat(name, entry)` — schedule a periodic task.
    * `register_context_processor(func)` — template context.
    """

    # ── Required metadata ──────────────────────────────────────────────────────
    name: str = ''  # unique snake_case — must match directory name
    label: str = ''  # human-readable name
    version: str = '1.0.0'
    description: str = ''
    author: str = 'Morph Team'
    url: str = ''  # plugin homepage / docs

    # ── Dependency graph ───────────────────────────────────────────────────────
    requires: list[str] = []  # plugin names this depends on
    conflicts: list[str] = []  # plugins this cannot coexist with

    # First-run activation: True (default) auto-enables the plugin the first
    # time it's discovered; False ships it installed-but-OFF so the merchant
    # opts in from Dashboard → Apps. Only affects the very first run (when no
    # PluginConfig row exists yet); after that the DB flag wins.
    enabled_by_default: bool = True

    # ── Capabilities ──────────────────────────────────────────────────────────
    has_models: bool = False  # True if plugin defines Django models

    # ── Internal ──────────────────────────────────────────────────────────────
    _registry: PluginRegistry | None = None
    _config_cache: dict | None = None

    # ── Class-time validation ──────────────────────────────────────────────────

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Allow intermediate base classes that don't set `name` (rare).
        if not cls.name:
            return
        cls._validate_metadata()

    @classmethod
    def _validate_metadata(cls) -> None:
        if not isinstance(cls.name, str) or not _NAME_RE.match(cls.name):
            raise PluginConfigurationError(
                f'{cls.__name__}.name must be a snake_case identifier '
                f'(letters, digits, underscores; start with a letter). Got {cls.name!r}.'
            )
        if not cls.label:
            raise PluginConfigurationError(
                f'{cls.__name__}.label is required (human-readable name).'
            )
        if not isinstance(cls.version, str) or not _VERSION_RE.match(cls.version):
            raise PluginConfigurationError(
                f'{cls.__name__}.version must look like 1.2.3 or 1.2.3a4. Got {cls.version!r}.'
            )
        if not isinstance(cls.requires, list) or any(not isinstance(x, str) for x in cls.requires):
            raise PluginConfigurationError(
                f'{cls.__name__}.requires must be a list of plugin name strings.'
            )
        if not isinstance(cls.conflicts, list) or any(
            not isinstance(x, str) for x in cls.conflicts
        ):
            raise PluginConfigurationError(
                f'{cls.__name__}.conflicts must be a list of plugin name strings.'
            )
        if not isinstance(cls.has_models, bool):
            raise PluginConfigurationError(f'{cls.__name__}.has_models must be True or False.')

    # ── Lifecycle (override these) ─────────────────────────────────────────────

    def ready(self) -> None:
        """Hook your registrations here. Called once per process boot."""

    def on_disable(self) -> None:
        """Tear-down hook. Called when a merchant disables the plugin."""

    # ── Registration helpers ───────────────────────────────────────────────────

    def register_urls(
        self,
        urlconf: str,
        prefix: str = '',
        namespace: str | None = None,
    ) -> None:
        """Mount a URLconf module under `prefix` with the given `namespace`."""
        if not isinstance(urlconf, str) or not urlconf:
            raise ValueError('register_urls: urlconf must be a non-empty module path.')
        if self._registry is None:
            raise RuntimeError(
                'register_urls called before plugin was activated. Move the call inside ready().'
            )
        self._registry.add_plugin_urls(
            urlconf,
            prefix=prefix,
            namespace=namespace or self.name,
        )

    def register_graphql_extension(self, module: str) -> None:
        """Register a Strawberry mixin module (`<X>QueryExtension`/`<X>MutationExtension`)."""
        if not isinstance(module, str) or not module:
            raise ValueError('register_graphql_extension: module must be a non-empty path.')
        if self._registry is None:
            raise RuntimeError('register_graphql_extension called before activation.')
        self._registry.add_graphql_extension(module)

    def register_hook(self, event: str, handler: Callable, priority: int = 50) -> None:
        """Subscribe a callable to a domain event. Lower priority runs first."""
        if not callable(handler):
            raise TypeError('register_hook: handler must be callable.')
        if not isinstance(event, str) or not event:
            raise ValueError('register_hook: event must be a non-empty string.')
        if not isinstance(priority, int):
            raise TypeError('register_hook: priority must be an int.')
        from core.hooks import hook_registry

        # Tag the subscription with the owning plugin so the bus skips it while
        # the plugin is disabled (ADR 0023) — deactivate() doesn't unwind hooks.
        hook_registry.register(event, handler, priority=priority, plugin=self.name)

    def register_admin(self, model: Any, admin_class: Any) -> None:
        """Register a Django admin entry. Idempotent; ignores AlreadyRegistered."""
        from django.contrib import admin as django_admin

        try:  # noqa: SIM105
            django_admin.site.register(model, admin_class)
        except django_admin.sites.AlreadyRegistered:
            pass

    def register_celery_tasks(self, module: str) -> None:
        """Make Celery aware of a tasks module from this plugin."""
        if self._registry is None:
            return
        self._registry.add_task_module(module)

    def register_context_processor(self, func: Callable) -> None:
        """Contribute a template context processor that runs on every request.

        Consumed at request time by the aggregator in
        `plugins/context_processors.py:plugin_context` (Django resolves the
        static TEMPLATES list at settings-import, before plugins load, so this
        lazy registration is invisible to a directly-listed processor). The
        aggregator skips this func while `self.name` is inactive, so the
        contributed context disappears when the plugin is disabled.
        """
        if not callable(func):
            raise TypeError('register_context_processor: func must be callable.')
        if self._registry is None:
            return
        self._registry.add_context_processor(func, plugin=self.name)

    def register_celery_beat(self, name: str, entry: dict) -> None:
        """Add a Celery beat schedule entry. Existing entries are not overwritten."""
        from django.conf import settings

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None)
        if schedule is None:
            return
        schedule.setdefault(name, entry)

    # ── Configuration ──────────────────────────────────────────────────────────

    def get_config_schema(self) -> dict:
        """JSON Schema for this plugin's settings (rendered as a form in admin)."""
        return {}

    def get_config(self) -> dict:
        """Read current config from DB (cached)."""
        from django.db import DatabaseError

        if self._config_cache is None:
            from plugins.models import PluginConfig

            try:
                row = PluginConfig.objects.get(plugin_name=self.name)
                self._config_cache = row.config or {}
            except (PluginConfig.DoesNotExist, DatabaseError):
                self._config_cache = {}
        return self._config_cache

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get one config value with fallback to schema default."""
        config = self.get_config()
        if key in config:
            return config[key]
        schema = self.get_config_schema()
        return schema.get('properties', {}).get(key, {}).get('default', default)

    def set_config(self, key: str, value: Any) -> None:
        """Persist one config value (and invalidate the cache)."""
        from plugins.models import PluginConfig

        row, _ = PluginConfig.objects.get_or_create(plugin_name=self.name)
        row.config[key] = value
        row.save(update_fields=['config', 'updated_at'])
        self._config_cache = None

    def invalidate_config_cache(self) -> None:
        self._config_cache = None

    # ── Contribution surfaces ─────────────────────────────────────────────────
    #
    # When the plugin is *enabled*, the registry collects the return values
    # of these three methods into platform-wide indexes. See
    # `plugins.contributions` for the dataclass shapes.

    def contribute_storefront_blocks(self) -> list:
        """Return a list of `StorefrontBlock` instances.

        The active theme decides which `slot` names it actually renders
        via `{% load morph %}{% storefront_blocks "slot_name" %}`. Empty
        list = no storefront contributions.
        """
        return []

    def contribute_dashboard_pages(self) -> list:
        """Return a list of `DashboardPage` entries.

        The registry mounts each at `/dashboard/apps/<plugin>/<slug>/` and
        the dashboard sidebar renders them in their declared `section`.
        """
        return []

    def contribute_settings_panel(self):
        """Return a `SettingsPanel` (or `None`).

        Override to expose this plugin's settings as a merchant-editable
        form on `/dashboard/apps/<plugin>/settings/`.
        """
        return None

    def contribute_email_templates(self) -> list:
        """Return a list of `EmailTemplateDef` — this plugin's transactional
        emails for the CENTRAL registry (Settings → Notifications → Email
        templates). Ship the default bodies as
        `templates/emails/<key>.{html,txt}` and send via
        `core.emails.send_templated_email(key, ...)`.
        """
        return []

    def contribute_agents(self) -> list:
        """Return a list of `MorpheusAgent` instances this plugin ships.

        Each agent is registered in `core.agents.agent_registry` and made
        available to platform UIs (storefront chat, merchant ops console,
        proactive listeners).
        """
        return []

    def contribute_agent_tools(self) -> list:
        """Return a list of `core.agents.Tool` instances this plugin exposes.

        Tools are scoped capabilities the agent layer can call (e.g.
        `inventory.reserve_stock`, `catalog.find_products`). Tools are
        independent of agents — any agent whose scopes cover the tool's
        scopes will be allowed to call it.
        """
        return []

    def contribute_skills(self) -> list:
        """Return a list of `core.agents.Skill` bundles this plugin exposes.

        A Skill is a named bundle of related tools + an optional system-prompt
        prelude. Agents opt in via `uses_skills = ('skill_name', ...)`. Use
        skills to package reusable agent capabilities (e.g. `storefront`,
        `catalog_admin`, `crm`) instead of duplicating tool lists across
        every agent that needs them.
        """
        return []

    # ── Info ──────────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f'<MorpheusPlugin: {self.name} v{self.version}>'
