"""
Morpheus CMS — Plugin Registry
Discovers, validates, loads, and manages the lifecycle of all plugins.
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
import uuid

from plugins.base import MorpheusPlugin

logger = logging.getLogger('morpheus.plugins')

# Every process keeps the apps that are on in memory, so a switch flipped in
# one web worker reaches the others through this token: the persisted
# `activate`/`deactivate` bump it, and each process's `reconcile()` (on every
# request and before every task) re-reads the stored switches when it changed.
# Same pattern as booking_marketplace's search index version.
_VERSION_KEY = 'plugins:active:version'
# A cache outage loses the bump, so a process re-reads the switches at most
# this often anyway (never under tests, where it would make results depend on
# timing).
DB_REREAD_S = 60


class AppRegistry:
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

    # Set once, by the first registry to wire the global hook active-check.
    # Guards against a throwaway instance rebinding the shared bus (hunt #12).
    _active_check_wired: bool = False

    def __init__(self) -> None:
        self._plugins: dict[str, MorpheusPlugin] = {}
        self._classes: dict[str, type[MorpheusPlugin]] = {}
        self._active: set[str] = set()
        # Plugins whose ready() has run this process. ready() wires hooks +
        # URLs, which disable does NOT unwind, so re-enabling must not run it
        # twice. activate() uses this to skip re-wiring on a re-enable.
        self._wired: set[str] = set()
        # Apps whose ready() raised in this process. `reconcile()` never tries
        # them again (a half-run ready() may have wired some hooks already);
        # an explicit `activate()` still may.
        self._failed: set[str] = set()
        # The switches token this process last read the database for. None until
        # the first `reconcile()`, which therefore always reads once: boot reads
        # the switches before the cache is reachable, and a switch flipped while
        # this process started must not be missed.
        self._seen_version: str | None = None
        self._last_db_read = 0.0
        # One switch at a time in this process: `activate`, `deactivate` and
        # `reconcile` all take it, so two threads never run an app's ready()
        # twice (its hooks would answer twice for the life of the worker). It is
        # re-entrant because an eager task inside ready() reconciles too.
        self._switch_lock = threading.RLock()
        # Whether `reconcile()` follows the stored switches. None means yes,
        # except under tests: hundreds of tests set an app's in-memory state by
        # hand (`_active.discard`) while its stored row says otherwise, and a
        # request or an eager task would then put it back, in an order that
        # depends on which test ran first. A test of the following itself turns
        # it on (`plugins.testing.follow_app_switches`).
        self.follow_switches: bool | None = None
        self._graphql_extensions: list[str] = []
        self._plugin_urls: list[dict] = []
        self._task_modules: list[str] = []
        self._context_processors: list = []
        # ── Contribution indexes ─────────────────────────────────────────────
        # Populated by `_collect_contributions(plugin)` after `ready()`.
        # See `plugins.contributions` for shapes.
        self._storefront_blocks: list = []  # [StorefrontBlock]
        self._dashboard_pages: list = []  # [DashboardPage]
        self._dashboard_cards: list = []  # [DashboardCard]
        self._settings_panels: dict = {}  # name -> SettingsPanel
        self._email_templates: list = []  # [EmailTemplateDef]
        self._plugin_skills: dict[str, list[str]] = {}  # plugin -> [skill.name]
        self._ready = False
        # Let the hook bus skip handlers owned by a disabled plugin, so a
        # plugin's contributed cards/KPIs/feed items vanish on disable even
        # though deactivate() doesn't unwind ready()-wired hooks (ADR 0023).
        #
        # Only the FIRST (canonical, module-level) registry wires the global
        # bus's active-check. A throwaway second instance — the 5 that
        # `plugins/tests.py` builds — would otherwise rebind the shared bus to
        # its own EMPTY `_active` set, silently gating every plugin handler off
        # process-wide (a latent test-isolation footgun; hunt #12).
        from core.hooks import hook_registry

        if not AppRegistry._active_check_wired:
            hook_registry.set_active_check(self.is_active)
            AppRegistry._active_check_wired = True

    # ── Discovery ──────────────────────────────────────────────────────────────

    def discover(self, plugin_module_paths: list[str]) -> None:
        for module_path in plugin_module_paths:
            try:
                mod = importlib.import_module(f'{module_path}.app')
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
        logger.warning('No MorpheusPlugin subclass found in %s.app', module_path)
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
        if self._apply_active(plugin.name):
            # Per-plugin success is DEBUG (still surfaces in dev / tracing);
            # the boot summary at the end of activate_all() carries the
            # human-readable count + names list at INFO.
            logger.debug('Plugin activated: %s v%s', plugin.name, plugin.version)

    # In-memory pair: this process only. No URL refresh (the caller does it
    # once), no database write, no token bump, no on_disable().

    def _apply_active(self, name: str) -> bool:
        """Switch an app on in this process. True if it is on afterwards.

        `ready()` wires hooks + URLs, which a disable does NOT unwind, so it runs
        once per process (`_wired`); a re-enable after a disable just re-collects
        the contributions `_drop_contributions` removed. A `ready()` that raises
        leaves the app off here, logged at ERROR.
        """
        instance = self._plugins.get(name)
        if instance is None:
            return False
        if name in self._active:
            return True
        if name not in self._wired:
            try:
                instance.ready()
            except Exception as e:  # noqa: BLE001 — a bad plugin must not bring down the app
                self._failed.add(name)
                logger.error('Failed to activate plugin %s: %s', name, e, exc_info=True)
                return False
            self._wired.add(name)
        self._failed.discard(name)
        self._active.add(name)
        self._collect_contributions(instance)
        return True

    def _apply_inactive(self, name: str) -> None:
        """Switch an app off in this process: its hooks stop answering (the bus
        asks `is_active`) and its contributions leave."""
        if name in self._active:
            self._active.discard(name)
            self._drop_contributions(name)

    # Persisted pair: the switch for the whole store. Stores it, bumps the
    # token every other process reconciles on, and (on disable) runs the app's
    # on_disable() — once, here, never in the processes that follow. A switch
    # the database did not save raises and leaves this process as it was:
    # reporting it as done would let this worker's next reconcile undo it.

    def deactivate(self, name: str, *, tear_down: bool | None = None) -> None:
        """Switch an app off for the store. Callers decide whether it may go
        (`plugins.services.set_enabled`); this only carries it out.

        `tear_down` says whether `on_disable()` runs; by default, when the app
        runs here. `set_enabled` passes whether the store had it on, so the
        tear-down still runs when the app's start-up failed in this process.
        Raises `DatabaseError` when the switch cannot be stored.
        """
        if name not in self._plugins:
            return
        with self._switch_lock:
            self._store_switch(name, enabled=False)
            if tear_down is None:
                tear_down = name in self._active
            if tear_down:
                try:
                    self._plugins[name].on_disable()
                except Exception as e:  # noqa: BLE001 — a failed tear-down never keeps an app on
                    logger.error('plugins: %s.on_disable failed: %s', name, e, exc_info=True)
            if name in self._active:
                self._apply_inactive(name)
                # Rebuild the live URLconf so this plugin's register_urls routes
                # stop resolving (get_urlpatterns now skips inactive owners);
                # without it a disabled plugin's endpoints keep serving (hunt #13).
                self._refresh_urlconf()
            self._bump_version()
        logger.info('Plugin deactivated: %s', name)

    def activate(self, name: str) -> bool:
        """Switch an app on for the store — the mirror of `deactivate()`.

        Returns True if the app is on afterwards. Its hooks, URLs, settings
        panel and other contributions light up here at once and in every other
        process at its next request or task (`reconcile`). When `ready()`
        raises here, nothing is stored: the app stays off everywhere. Raises
        `DatabaseError` when the switch cannot be stored, after switching the
        app back off here.
        """
        if name not in self._plugins:
            return False
        with self._switch_lock:
            started_here = name not in self._active
            if started_here:
                if not self._apply_active(name):
                    return False
                # Re-mount URLs *after* marking active and on *every* enable:
                # `get_urlpatterns` skips inactive owners, so a refresh before
                # `_active.add` filtered out the very routes being enabled.
                self._refresh_urlconf()
            try:
                self._store_switch(name, enabled=True)
            except Exception:
                if started_here:
                    self._apply_inactive(name)
                    self._refresh_urlconf()
                raise
            self._bump_version()
        logger.info('Plugin activated at runtime: %s', name)
        return True

    # ── Every process follows the stored switches ─────────────────────────────

    def _version(self) -> str:
        from django.core.cache import cache

        try:
            current = cache.get(_VERSION_KEY)
            if current is None:
                cache.add(_VERSION_KEY, uuid.uuid4().hex, None)
                current = cache.get(_VERSION_KEY)
        except Exception:  # noqa: BLE001 — without the cache the timed re-read still runs
            return ''
        return current or ''

    def _bump_version(self) -> None:
        """Tell every other process to re-read the switches. This process does
        not mark the new token as read: another switch flipped elsewhere a
        moment before would otherwise hide behind it, so its next reconcile
        reads the database once more."""
        from django.core.cache import cache

        try:
            cache.set(_VERSION_KEY, uuid.uuid4().hex, None)
        except Exception:  # noqa: BLE001 — the timed re-read covers a cache outage
            logger.warning('plugins: could not bump the switches version', exc_info=True)

    def _following(self) -> bool:
        if self.follow_switches is not None:
            return self.follow_switches
        from django.conf import settings

        return not getattr(settings, '_RUNNING_TESTS', False)

    def _reread_due(self) -> bool:
        from django.conf import settings

        if getattr(settings, '_RUNNING_TESTS', False):
            return False
        return time.monotonic() - self._last_db_read > DB_REREAD_S

    def _stored_switches(self) -> dict[str, bool] | None:
        """``{app: is_enabled}`` as stored, read only; None when the database
        cannot answer. An app with no row has no stored switch (boot writes one
        for every app it finds, so on a store that means it was never there)."""
        from django.db import DEFAULT_DB_ALIAS, DatabaseError

        try:
            from plugins.models import PluginConfig

            # From the primary: a lagging replica would mark the new token read
            # with the old switches, and undo this worker's own click.
            rows = PluginConfig.objects.using(DEFAULT_DB_ALIAS)
            return dict(rows.values_list('plugin_name', 'is_enabled'))
        except (DatabaseError, ImportError, LookupError):
            return None

    def _keeps_running(self, name: str) -> bool:
        """An app reconcile never switches off: a system app, or one the store
        cannot run without (`core.safety.protection_reason`, the same gate every
        disable asks). A stored "off" for it is a mistake, not an instruction."""
        cls = self._classes.get(name)
        if cls is not None and getattr(cls, 'system', False):
            return True
        try:
            from core.safety import is_plugin_protected

            return is_plugin_protected(name)
        except Exception:  # noqa: BLE001 — when in doubt, leave it running
            return True

    def reconcile(self) -> None:
        """Bring this process in line with the stored switches.

        Called before every request (`PluginMiddleware`) and every Celery task.
        Costs one cache read while nothing changed. When the token moved (or,
        outside tests, every `DB_REREAD_S`), it reads the switches under a lock
        and applies the difference in dependency order, then refreshes the URLs
        once. It never writes a switch, never bumps the token, never runs
        `on_disable()` (that ran once, where the switch was flipped) and never
        switches off a system or protected app. An app it switches on runs its
        `ready()` here, which may do the app's own start-up work.
        """
        if not self._ready or not self._following():
            return
        version = self._version()
        if version == self._seen_version and not self._reread_due():
            return
        with self._switch_lock:
            version = self._version()
            if version == self._seen_version and not self._reread_due():
                return  # another thread did it while this one waited
            stored = self._stored_switches()
            self._last_db_read = time.monotonic()
            if stored is None:
                return  # the token stays unread, so the next call tries again
            try:
                self._apply_switches(stored)
            finally:
                # Marked read only once applied: a thread that arrives meanwhile
                # waits on the lock instead of serving on a half-applied set.
                self._seen_version = version

    def _apply_switches(self, stored: dict[str, bool]) -> None:
        try:
            order = self._topo_sort(list(self._classes))
        except ValueError:
            order = sorted(self._classes)
        known = [n for n in order if n in self._plugins and n in stored]
        off = [
            n
            for n in reversed(known)
            if not stored[n] and n in self._active and not self._keeps_running(n)
        ]
        on = [n for n in known if stored[n] and n not in self._active and n not in self._failed]
        for name in off:
            self._apply_inactive(name)
        switched_on = [name for name in on if self._apply_active(name)]
        if off or switched_on:
            self._refresh_urlconf()
            logger.info(
                'plugins: followed the stored switches (on: %s; off: %s)',
                ', '.join(switched_on) or '-',
                ', '.join(off) or '-',
            )

    # The URL modules the root urlconf actually includes, with the surface
    # filter each one applies. `morph/urls.py` mounts `plugins.chrome_urls`
    # (dashboard/api/payments — never language-prefixed) and
    # `plugins.storefront_urls` (inside i18n_patterns) — ADR 0022. `plugins.urls`
    # is the pre-split module, kept for anything out of tree that includes it.
    _URL_MODULES: tuple[tuple[str, dict], ...] = (
        ('plugins.chrome_urls', {'storefront': False}),
        ('plugins.storefront_urls', {'storefront': True}),
        ('plugins.urls', {}),
    )

    def _refresh_urlconf(self) -> None:
        """Re-mount plugin URLs into the live URLconf after a runtime toggle.

        Each URL module's `urlpatterns` is built once, when the root urlconf
        first imports it. A plugin enabled at runtime added its entry to
        `_plugin_urls` during `ready()`; a disabled one must stop resolving. So
        rebuild each *already-imported* module's list **in place** — the live
        resolvers hold a reference to that very list — and clear Django's
        resolver caches so the next request re-populates from it. Modules not
        yet imported are skipped: they will compute the right list on import.

        This used to rebuild only `plugins.urls`, which nothing has included
        since the ADR 0022 split, so a runtime disable never reached the live
        resolver: the plugin's endpoints kept serving until the next restart —
        and a template still reversing one of its routes then 500'd on boot.
        Guarded by `core/tests/test_registry_url_disable.py::LiveResolverDisableTests`.
        """
        try:
            import sys

            from django.urls import clear_url_caches

            for mod_name, kwargs in self._URL_MODULES:
                mod = sys.modules.get(mod_name)
                if mod is not None:
                    mod.urlpatterns[:] = self.get_urlpatterns(**kwargs)
            clear_url_caches()
        except Exception as e:  # noqa: BLE001 — URL refresh failure must not break the toggle
            logger.warning('Failed to refresh URLconf after toggle: %s', e, exc_info=True)

    # ── Contributions ─────────────────────────────────────────────────────────

    def _collect_list(self, plugin: MorpheusPlugin, method: str, index: list) -> None:
        """Append one `contribute_*` list to its index, owner-tagged. A plugin
        whose method raises loses that one surface, never its activation."""
        try:
            for item in getattr(plugin, method)() or []:
                item.plugin = plugin.name
                index.append(item)
        except Exception as e:  # noqa: BLE001
            logger.warning('plugins: %s.%s failed: %s', plugin.name, method, e, exc_info=True)

    def _collect_contributions(self, plugin: MorpheusPlugin) -> None:
        """Pull `contribute_*` results from a plugin and merge them into
        the platform-wide indexes. Failures are logged and swallowed —
        a misbehaving plugin should not break activation."""
        self._collect_list(plugin, 'contribute_storefront_blocks', self._storefront_blocks)
        self._collect_list(plugin, 'contribute_dashboard_pages', self._dashboard_pages)
        self._collect_list(plugin, 'contribute_dashboard_cards', self._dashboard_cards)
        self._collect_list(plugin, 'contribute_email_templates', self._email_templates)
        try:
            panel = plugin.contribute_settings_panel()
            if panel is not None:
                panel.plugin = plugin.name
                # A new dict, like the lists below: other threads may be iterating it.
                self._settings_panels = {**self._settings_panels, plugin.name: panel}
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
                # Track ownership so disable can unregister it — SkillRegistry
                # keeps no owner of its own (hunt #14).
                self._plugin_skills.setdefault(plugin.name, []).append(skill.name)
            for agent in plugin.contribute_agents() or []:
                agent_registry.register_agent(agent, plugin=plugin.name)
        except Exception as e:  # noqa: BLE001
            logger.warning(
                'plugins: %s agent contributions failed: %s', plugin.name, e, exc_info=True
            )
        # Sort blocks and pages once per activation so render-time stays cheap.
        # Into new lists: an app now also switches on while other threads of the
        # same worker render (`reconcile`), and a list being sorted in place
        # reads as empty to them.
        self._storefront_blocks = sorted(
            self._storefront_blocks, key=lambda b: (b.slot, b.priority, b.plugin)
        )
        self._dashboard_pages = sorted(
            self._dashboard_pages, key=lambda p: (p.section, p.order, p.label)
        )
        self._dashboard_cards = sorted(
            self._dashboard_cards, key=lambda c: (c.section, c.order, c.title)
        )

    def _drop_contributions(self, plugin_name: str) -> None:
        self._storefront_blocks = [b for b in self._storefront_blocks if b.plugin != plugin_name]
        self._dashboard_pages = [p for p in self._dashboard_pages if p.plugin != plugin_name]
        self._dashboard_cards = [c for c in self._dashboard_cards if c.plugin != plugin_name]
        self._email_templates = [t for t in self._email_templates if t.plugin != plugin_name]
        self._settings_panels = {
            name: panel for name, panel in self._settings_panels.items() if name != plugin_name
        }
        try:
            from core.agents.registry import agent_registry
            from core.agents.skills import skill_registry

            agent_registry.drop_plugin(plugin_name)
            # Unregister the plugin's contributed skills too — otherwise a
            # disabled plugin's skill (and the tools it re-injects) stay
            # resolvable, leaking a capability the merchant turned off (hunt #14).
            for skill_name in self._plugin_skills.pop(plugin_name, []):
                skill_registry.unregister(skill_name)
        except Exception as e:  # noqa: BLE001
            logger.warning('plugins: %s agent drop failed: %s', plugin_name, e, exc_info=True)

    def storefront_blocks_for(self, slot: str) -> list:
        return [b for b in self._storefront_blocks if b.slot == slot]

    def dashboard_pages(self, section: str | None = None) -> list:
        if section is None:
            return list(self._dashboard_pages)
        return [p for p in self._dashboard_pages if p.section == section]

    def dashboard_url_mounts(self) -> list[tuple[str, str]]:
        """``(app, '/dashboard/<prefix>/')`` for every active app that mounts
        its own routes under the dashboard. The dashboard uses them to tell
        which app a detail page belongs to; the shell's own ``dashboard/``
        mount is not an app's and is left out."""
        out = []
        for entry in self._plugin_urls:
            prefix = entry.get('prefix') or ''
            owner = entry.get('plugin') or ''
            if not owner or prefix == 'dashboard/' or not prefix.startswith('dashboard/'):
                continue
            if self.is_active(owner):
                out.append((owner, '/' + prefix))
        return out

    def url_prefixes(self, name: str) -> list[str]:
        """The URL prefixes an app mounts its own routes under ('/' for the root)."""
        return [
            '/' + (entry.get('prefix') or '')
            for entry in self._plugin_urls
            if entry.get('plugin') == name
        ]

    def dashboard_cards(self, section: str | None = None) -> list:
        """Contributed `DashboardCard`s, sorted by section then order. Raw
        `section` values — the dashboard resolves legacy aliases itself."""
        if section is None:
            return list(self._dashboard_cards)
        return [c for c in self._dashboard_cards if c.section == section]

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

    def _store_switch(self, name: str, enabled: bool) -> None:
        """Store an app's switch. Raises `DatabaseError` when it cannot: a switch
        the store did not save must never be reported as switched."""
        from plugins.models import PluginConfig

        PluginConfig.objects.update_or_create(plugin_name=name, defaults={'is_enabled': enabled})

    # ── Registration (called by plugin.ready()) ────────────────────────────────

    def add_graphql_extension(self, module: str) -> None:
        if module not in self._graphql_extensions:
            self._graphql_extensions.append(module)

    def add_plugin_urls(
        self,
        urlconf: str,
        prefix: str = '',
        namespace: str = '',
        plugin: str = '',
        surface: str | None = None,
    ) -> None:
        """Record a plugin URLconf mount.

        ``surface`` decides whether the routes get language-prefixed (ADR 0022):
        ``'storefront'`` → wrapped in ``i18n_patterns``; ``'chrome'`` → never.
        It defaults to the historical rule "mounted at prefix '' ⇒ storefront",
        which is right for pages but wrong for machine endpoints mounted at the
        root: robots.txt, sitemap.xml and llms.txt were resolving at ``/fr/…``
        too, publishing a second copy of every discovery file per language.
        """
        if surface not in ('storefront', 'chrome', None):
            raise ValueError(
                f"add_plugin_urls: surface must be 'storefront'|'chrome', got {surface!r}"
            )
        self._plugin_urls.append(
            {
                'urlconf': urlconf,
                'prefix': prefix,
                'namespace': namespace,
                'plugin': plugin,
                'surface': surface or ('storefront' if prefix == '' else 'chrome'),
            }
        )

    def add_task_module(self, module: str) -> None:
        if module not in self._task_modules:
            self._task_modules.append(module)

    def add_context_processor(self, func, plugin: str | None = None) -> None:
        """Record a plugin-contributed context processor as (func, owner). The
        owner lets the request-time aggregator (plugins/context_processors.py)
        skip it while its plugin is inactive — context processors are resolved
        statically by Django and are NOT bus-gated like hooks."""
        self._context_processors.append((func, plugin))

    def context_processors(self) -> list:
        """The (func, owner) context processors plugins contributed via
        `register_context_processor`. Consumed by the request-time aggregator;
        Django never sees these directly (its TEMPLATES list is fixed at
        settings-import, before plugins load)."""
        return list(self._context_processors)

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
          * ``True``  → only storefront entries.
          * ``False`` → only chrome entries (dashboard/, api/, payments/, …, and
            root-mounted machine endpoints like robots.txt), which stay
            UNPREFIXED.

        The surface comes from the mount's declared ``surface`` (see
        ``add_plugin_urls``), which defaults to the old prefix-based rule.
        """
        from django.urls import include, path

        # Deeper prefixes mount FIRST (stable sort — ties keep registration
        # order, so the documented first-registrant-wins rule still holds for
        # equal prefixes). Without this, a shallow include swallows every
        # sibling mounted under its subtree: admin_dashboard's `dashboard/`
        # urlconf carries the `apps/<str:plugin>/<slug:slug>/` app-discovery
        # router and registered before the plugins it routes FOR, so a plugin's
        # own `dashboard/apps/<name>/<route>/` mount was unreachable whenever
        # <route> wasn't one of its DashboardPage slugs — bookvault's
        # connect/disconnect shipped dead this way, and feedback had to nest
        # its routes a segment deeper to dodge it. Depth-first mounting makes
        # the discovery router what it was meant to be: a fallback. (Known,
        # intended flip: demo_data's own `settings/` route now beats the
        # legacy plugin-settings 301 that shadowed it.)
        def _depth(entry) -> int:
            prefix = entry.get('prefix') or ''
            return len([seg for seg in prefix.split('/') if seg])

        patterns = []
        for entry in sorted(self._plugin_urls, key=_depth, reverse=True):
            # Skip routes owned by a disabled plugin so its endpoints stop
            # resolving on disable — register_urls mounts stay in _plugin_urls
            # across a deactivate (like ready()-wired hooks), so without this an
            # optional plugin's customer-facing URLs (e.g. digital_products'
            # /account/downloads/) keep serving after it's toggled off, failing
            # the disable litmus test (hunt #13). Untagged (plugin='') entries
            # are always included (core/back-compat).
            owner = entry.get('plugin')
            if owner and not self.is_active(owner):
                continue
            is_storefront = (
                entry.get('surface', 'storefront' if entry['prefix'] == '' else 'chrome')
                == 'storefront'
            )
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

    def config_value(self, name: str, key: str, default=None):
        """One plugin's config value, fail-soft.

        Returns ``default`` when the plugin is absent or any lookup error
        occurs, so a config read can never crash the caller (checkout, payment,
        rendering). Collapses the registry-get + None-guard + try/except that
        was hand-rolled at every call site — a site that forgets the guard is
        exactly how a config read takes down a payment flow.
        """
        try:
            plugin = self._plugins.get(name)
            return plugin.get_config_value(key, default) if plugin is not None else default
        except Exception:  # noqa: BLE001 — a config read must never break a caller
            return default

    def is_active(self, name: str) -> bool:
        return name in self._active

    def all_plugins(self) -> list[MorpheusPlugin]:
        return list(self._plugins.values())

    def active_plugins(self) -> list[MorpheusPlugin]:
        return [p for p in self._plugins.values() if p.name in self._active]

    def __repr__(self) -> str:
        return f'<AppRegistry: {len(self._plugins)} plugins, {len(self._active)} active>'


app_registry = AppRegistry()
