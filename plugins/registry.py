"""
Morpheus CMS — Plugin Registry
Discovers, validates, loads, and manages the lifecycle of all plugins.
"""

from __future__ import annotations

import importlib
import logging

from plugins.base import MorpheusPlugin

logger = logging.getLogger('morpheus.plugins')


class PluginRegistry:
    """
    Central registry for all Morph plugins.

    Responsibilities:
    - Discover plugin classes from `plugins/installed/`.
    - Validate the dependency graph (`requires`/`conflicts`).
    - Activate plugins in topologically-sorted order so dependencies are
      ready before dependents call `ready()`.
    - Aggregate GraphQL extensions for schema assembly.
    - Aggregate plugin URL patterns.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, MorpheusPlugin] = {}
        self._classes: dict[str, type[MorpheusPlugin]] = {}
        self._active: set[str] = set()
        # Plugins whose ready() has run this process. ready() wires hooks +
        # URLs, which disable does NOT unwind, so re-enabling must not run it
        # twice. activate() uses this to skip re-wiring on a re-enable.
        self._wired: set[str] = set()
        self._graphql_extensions: list[str] = []
        self._plugin_urls: list[dict] = []
        self._task_modules: list[str] = []
        self._context_processors: list = []
        # ── Contribution indexes ─────────────────────────────────────────────
        # Populated by `_collect_contributions(plugin)` after `ready()`.
        # See `plugins.contributions` for shapes.
        self._storefront_blocks: list = []  # [StorefrontBlock]
        self._dashboard_pages: list = []  # [DashboardPage]
        self._settings_panels: dict = {}  # name -> SettingsPanel
        self._email_templates: list = []  # [EmailTemplateDef]
        self._ready = False
        # Let the hook bus skip handlers owned by a disabled plugin, so a
        # plugin's contributed cards/KPIs/feed items vanish on disable even
        # though deactivate() doesn't unwind ready()-wired hooks (ADR 0023).
        from core.hooks import hook_registry

        hook_registry.set_active_check(self.is_active)

    # ── Discovery ──────────────────────────────────────────────────────────────

    def discover(self, plugin_module_paths: list[str]) -> None:
        for module_path in plugin_module_paths:
            try:
                mod = importlib.import_module(f'{module_path}.plugin')
            except ImportError as e:
                logger.error('Failed to import plugin %s: %s', module_path, e, exc_info=True)
                continue
            plugin_class = self._find_plugin_class(mod, module_path)
            if plugin_class:
                self._classes[plugin_class.name] = plugin_class
                logger.debug('Discovered plugin: %s (%s)', plugin_class.name, module_path)

    def _find_plugin_class(self, module, module_path: str) -> type[MorpheusPlugin] | None:
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, MorpheusPlugin)
                and obj is not MorpheusPlugin
                and obj.name
            ):
                return obj
        logger.warning('No MorpheusPlugin subclass found in %s.plugin', module_path)
        return None

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> list[str]:
        from django.apps import apps as _django_apps

        errors: list[str] = []
        for name, cls in self._classes.items():
            for dep in cls.requires:
                if dep in self._classes:
                    continue
                # A `core.*` dependency is a core Django app, not a plugin —
                # it's satisfied when it's in INSTALLED_APPS (core apps always
                # are). Without this, `requires=['core.audit']` falsely reports
                # 'not installed' on every boot even though it's present.
                if dep.startswith('core.') and _django_apps.is_installed(dep):
                    continue
                errors.append(f"Plugin '{name}' requires '{dep}' which is not installed.")
            for conflict in cls.conflicts:
                if conflict in self._classes:
                    errors.append(
                        f"Plugin '{name}' conflicts with '{conflict}' — both are installed."
                    )
        try:
            self._topo_sort(list(self._classes.keys()))
        except ValueError as e:
            errors.append(str(e))
        return errors

    def _topo_sort(self, names: list[str]) -> list[str]:
        """Topologically order plugin names by `requires` (Kahn's algorithm)."""
        from collections import deque

        in_degree: dict[str, int] = {n: 0 for n in names}
        edges: dict[str, list[str]] = {n: [] for n in names}
        for name in names:
            cls = self._classes[name]
            for dep in cls.requires:
                if dep not in in_degree:
                    continue
                edges[dep].append(name)
                in_degree[name] += 1

        # Stable order: feed the queue alphabetically so activation order is deterministic.
        queue = deque(sorted(n for n in names if in_degree[n] == 0))
        ordered: list[str] = []
        while queue:
            n = queue.popleft()
            ordered.append(n)
            for child in sorted(edges[n]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(ordered) != len(names):
            cycle = [n for n, deg in in_degree.items() if deg > 0]
            raise ValueError(f'Circular plugin dependency detected among: {cycle}')
        return ordered

    # ── Activation ────────────────────────────────────────────────────────────

    def activate_all(self) -> None:
        if self._ready:
            return

        errors = self.validate()
        if errors:
            for err in errors:
                logger.error('Plugin validation error: %s', err)

        try:
            order = self._topo_sort(list(self._classes.keys()))
        except ValueError as e:
            logger.error('%s — falling back to alphabetical order.', e)
            order = sorted(self._classes.keys())

        enabled_names = self._get_enabled_from_db()

        for name in order:
            cls = self._classes[name]
            instance = cls()
            instance._registry = self
            self._plugins[name] = instance

            if name in enabled_names:
                self._activate(instance)

        self._ready = True
        # One summary line at INFO. Per-plugin lines stay at DEBUG so
        # production logs don't get N lines of "Plugin activated:" noise
        # on every shell invocation.
        active = sorted(self._active)
        logger.info(
            'Plugin system ready: %d active (%s)',
            len(active),
            ', '.join(active),
        )

    def _activate(self, plugin: MorpheusPlugin) -> None:
        try:
            plugin.ready()
        except Exception as e:  # noqa: BLE001 — bad plugin must not bring down the app
            logger.error('Failed to activate plugin %s: %s', plugin.name, e, exc_info=True)
            return
        self._wired.add(plugin.name)
        self._active.add(plugin.name)
        self._collect_contributions(plugin)
        # Per-plugin success is DEBUG (still surfaces in dev / tracing);
        # the boot summary at the end of activate_all() carries the
        # human-readable count + names list at INFO.
        logger.debug('Plugin activated: %s v%s', plugin.name, plugin.version)

    def deactivate(self, name: str) -> None:
        if name in self._plugins and name in self._active:
            self._plugins[name].on_disable()
            self._active.discard(name)
            self._drop_contributions(name)
            self._update_db_status(name, enabled=False)
            logger.info('Plugin deactivated: %s', name)

    def activate(self, name: str) -> bool:
        """Enable a plugin at runtime — the mirror of `deactivate()`.

        Returns True if the plugin is active afterwards. Used by the dashboard
        apps toggle so enabling a plugin lights up its hooks, URLs, settings
        panel and other contributions immediately, without a server restart.

        Idempotency: `ready()` wires hooks + URLs, which `deactivate()` does
        NOT unwind, so running it twice would double-register them. We track
        wired plugins in `self._wired` and only run `ready()` (and re-mount
        URLs) on the first activation this process; a re-enable after a disable
        just re-collects the contributions that `_drop_contributions` removed.

        Caveat: a plugin that contributes process-level config fixed at boot
        (middleware, settings) still needs a restart for those parts — the
        apps view keeps surfacing the "restart" pill while `name not in
        _active`, which stays true if activation here fails.
        """
        instance = self._plugins.get(name)
        if instance is None:
            return False
        if name in self._active:
            return True
        if name not in self._wired:
            try:
                instance.ready()
            except Exception as e:  # noqa: BLE001 — a bad plugin must not break the toggle
                logger.error('Failed to activate plugin %s: %s', name, e, exc_info=True)
                return False
            self._wired.add(name)
            self._refresh_urlconf()
        self._active.add(name)
        self._collect_contributions(instance)
        self._update_db_status(name, enabled=True)
        logger.info('Plugin activated at runtime: %s', name)
        return True

    def _refresh_urlconf(self) -> None:
        """Re-mount plugin URLs into the live URLconf after a runtime enable.

        `plugins.urls.urlpatterns` is built once (at first request) from
        `get_urlpatterns()`. A plugin enabled at runtime added its entry to
        `_plugin_urls` during `ready()`, so rebuild that module list in place
        and clear Django's resolver caches; the next request rebuilds the root
        resolver and re-reads the updated patterns. No-op at boot (the urlconf
        isn't imported yet)."""
        try:
            from importlib import import_module

            from django.urls import clear_url_caches

            urls_mod = import_module('plugins.urls')
            urls_mod.urlpatterns[:] = self.get_urlpatterns()
            clear_url_caches()
        except Exception as e:  # noqa: BLE001 — URL refresh failure must not break the toggle
            logger.warning('Failed to refresh URLconf after activate: %s', e, exc_info=True)

    # ── Contributions ─────────────────────────────────────────────────────────

    def _collect_contributions(self, plugin: MorpheusPlugin) -> None:
        """Pull `contribute_*` results from a plugin and merge them into
        the platform-wide indexes. Failures are logged and swallowed —
        a misbehaving plugin should not break activation."""
        try:
            for block in plugin.contribute_storefront_blocks() or []:
                block.plugin = plugin.name
                self._storefront_blocks.append(block)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s.contribute_storefront_blocks failed: %s', plugin.name, e, exc_info=True
            )
        try:
            for page in plugin.contribute_dashboard_pages() or []:
                page.plugin = plugin.name
                self._dashboard_pages.append(page)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s.contribute_dashboard_pages failed: %s', plugin.name, e, exc_info=True
            )
        try:
            for tpl in plugin.contribute_email_templates() or []:
                tpl.plugin = plugin.name
                self._email_templates.append(tpl)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s.contribute_email_templates failed: %s', plugin.name, e, exc_info=True
            )
        try:
            panel = plugin.contribute_settings_panel()
            if panel is not None:
                panel.plugin = plugin.name
                self._settings_panels[plugin.name] = panel
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s.contribute_settings_panel failed: %s', plugin.name, e, exc_info=True
            )
        # Agent layer contributions — tools first so any agent that depends
        # on a sibling tool finds it already registered.
        try:
            from core.agents.registry import agent_registry
            from core.agents.skills import skill_registry

            for tool in plugin.contribute_agent_tools() or []:
                agent_registry.register_tool(tool, plugin=plugin.name)
            for skill in plugin.contribute_skills() or []:
                skill_registry.register(skill)
            for agent in plugin.contribute_agents() or []:
                agent_registry.register_agent(agent, plugin=plugin.name)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s agent contributions failed: %s', plugin.name, e, exc_info=True
            )
        # Sort blocks and pages once per activation so render-time stays cheap.
        self._storefront_blocks.sort(key=lambda b: (b.slot, b.priority, b.plugin))
        self._dashboard_pages.sort(key=lambda p: (p.section, p.order, p.label))

    def _drop_contributions(self, plugin_name: str) -> None:
        self._storefront_blocks = [b for b in self._storefront_blocks if b.plugin != plugin_name]
        self._dashboard_pages = [p for p in self._dashboard_pages if p.plugin != plugin_name]
        self._email_templates = [t for t in self._email_templates if t.plugin != plugin_name]
        self._settings_panels.pop(plugin_name, None)
        try:
            from core.agents.registry import agent_registry

            agent_registry.drop_plugin(plugin_name)
        except Exception as e:  # noqa: BLE001
            logger.warning('plugins: %s agent drop failed: %s', plugin_name, e, exc_info=True)

    def storefront_blocks_for(self, slot: str) -> list:
        return [b for b in self._storefront_blocks if b.slot == slot]

    def dashboard_pages(self, section: str | None = None) -> list:
        if section is None:
            return list(self._dashboard_pages)
        return [p for p in self._dashboard_pages if p.section == section]

    def email_templates(self) -> list:
        """Every active plugin's contributed email templates (EmailTemplateDef),
        sorted by group then label — for the central email-templates list."""
        return sorted(self._email_templates, key=lambda t: (t.group, t.label))

    def settings_panel(self, plugin_name: str):
        return self._settings_panels.get(plugin_name)

    def all_settings_panels(self) -> list:
        """Sorted list of (plugin_name, SettingsPanel) tuples — template-safe."""
        return [
            {'plugin': name, 'panel': panel}
            for name, panel in sorted(self._settings_panels.items(), key=lambda kv: kv[0])
        ]

    def _get_enabled_from_db(self) -> set[str]:
        from django.db import DatabaseError

        try:
            from plugins.models import PluginConfig

            existing_rows = list(PluginConfig.objects.values_list('plugin_name', 'is_enabled'))
        except (DatabaseError, ImportError, LookupError):
            logger.warning('PluginConfig table unavailable — activating all discovered plugins.')
            return set(self._classes.keys())

        existing_names = {name for name, _ in existing_rows}
        enabled = {name for name, is_enabled in existing_rows if is_enabled}

        # Newly discovered plugins (not yet in DB) default to enabled UNLESS the
        # manifest opts out (enabled_by_default=False → installed-but-OFF). Write
        # a row either way so the plugin shows up in the merchant admin and can
        # be toggled later.
        new_names = set(self._classes.keys()) - existing_names
        if new_names:
            try:
                from plugins.models import PluginConfig

                rows = []
                for n in new_names:
                    default_on = getattr(self._classes[n], 'enabled_by_default', True)
                    rows.append(PluginConfig(plugin_name=n, is_enabled=default_on))
                    if default_on:
                        enabled.add(n)
                PluginConfig.objects.bulk_create(rows, ignore_conflicts=True)
                logger.info(
                    'plugins: registered %s on first run (enabled: %s)',
                    sorted(new_names),
                    sorted(
                        n
                        for n in new_names
                        if getattr(self._classes[n], 'enabled_by_default', True)
                    ),
                )
            except DatabaseError as e:
                logger.warning('plugins: could not register new PluginConfig rows: %s', e)

        return enabled

    def _update_db_status(self, name: str, enabled: bool) -> None:
        from django.db import DatabaseError

        try:
            from plugins.models import PluginConfig

            PluginConfig.objects.update_or_create(
                plugin_name=name,
                defaults={'is_enabled': enabled},
            )
        except (DatabaseError, ImportError) as e:
            logger.error('Failed to update DB status for plugin %s: %s', name, e)

    # ── Registration (called by plugin.ready()) ────────────────────────────────

    def add_graphql_extension(self, module: str) -> None:
        if module not in self._graphql_extensions:
            self._graphql_extensions.append(module)

    def add_plugin_urls(self, urlconf: str, prefix: str = '', namespace: str = '') -> None:
        self._plugin_urls.append({'urlconf': urlconf, 'prefix': prefix, 'namespace': namespace})

    def add_task_module(self, module: str) -> None:
        if module not in self._task_modules:
            self._task_modules.append(module)

    def add_context_processor(self, func) -> None:
        self._context_processors.append(func)

    # ── GraphQL schema assembly ────────────────────────────────────────────────

    def get_graphql_extensions(self, extension_type: str) -> list[type]:
        bases: list[type] = []
        suffix = extension_type.capitalize() + 'Extension'
        for module_path in self._graphql_extensions:
            try:
                mod = importlib.import_module(module_path)
            except ImportError as e:
                logger.error('Failed to load GQL extension %s: %s', module_path, e, exc_info=True)
                continue
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and attr.endswith(suffix) and obj not in bases:
                    bases.append(obj)
        return bases

    # ── URL aggregation ───────────────────────────────────────────────────────

    def get_urlpatterns(self, *, storefront: bool | None = None):
        """Build plugin URL patterns.

        ``storefront`` filters by surface so the root urlconf can language-prefix
        only customer-facing pages (Phase 1b localization, ADR 0022):
          * ``None``  → every plugin URL (back-compat).
          * ``True``  → only storefront entries (registered at prefix '').
          * ``False`` → only chrome entries (dashboard/, api/, payments/, …),
            which must stay UNPREFIXED.
        """
        from django.urls import include, path

        patterns = []
        for entry in self._plugin_urls:
            is_storefront = entry['prefix'] == ''
            if storefront is True and not is_storefront:
                continue
            if storefront is False and is_storefront:
                continue
            try:
                patterns.append(
                    path(
                        entry['prefix'],
                        include((entry['urlconf'], entry['namespace'])),
                    )
                )
            except Exception as e:  # noqa: BLE001 — log misconfigured URLs, keep app booting
                logger.error('Failed to include URLs %s: %s', entry, e)
        return patterns

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get(self, name: str) -> MorpheusPlugin | None:
        return self._plugins.get(name)

    def is_active(self, name: str) -> bool:
        return name in self._active

    def all_plugins(self) -> list[MorpheusPlugin]:
        return list(self._plugins.values())

    def active_plugins(self) -> list[MorpheusPlugin]:
        return [p for p in self._plugins.values() if p.name in self._active]

    def __repr__(self) -> str:
        return f'<PluginRegistry: {len(self._plugins)} plugins, {len(self._active)} active>'


plugin_registry = PluginRegistry()
