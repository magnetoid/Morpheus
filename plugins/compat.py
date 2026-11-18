"""Whether an app can run on this store, and its upgrade step (v0.179.0).

**Compatibility.** An app's manifest may name the oldest and newest Morpheus it
runs on (`min_morpheus` / `max_morpheus`, both optional and inclusive). A bound
compares as many parts as it names, so `max_morpheus = '0.179'` allows every
0.179.x and `min_morpheus = '0.179.2'` refuses 0.179.1. A store whose own version
cannot be read (a development checkout saying 'unknown') runs every app.

The registry starts no app that this module says cannot run, and records why
in `app_registry.skipped` (shown on the Apps page and in `plugins.list`).
Protected and system apps are the exception: they always start, because the
store does not work without them (`AppRegistry._keeps_running`).

**Upgrades.** `PluginConfig.installed_version` holds the version of each app the
store last ran. After every migrate (each deploy runs one), `run_upgrades`
compares it with the running code. The new version is written and the app's
`on_upgrade(previous)` runs in one transaction: of every process that runs this
at once, the one whose compare-and-swap moves the row runs the step (the others
wait on the row's lock and then move nothing), and a step that fails, or a
process killed while it runs, leaves the old version so the next migrate tries
again. A store that updates its code in place (a git self-update, never a
container deploy) runs the step at its next migrate after the restart.
"""

from __future__ import annotations

import logging
import re

from core.update_sources import parse_version

logger = logging.getLogger('morpheus.plugins')

#: `PluginConfig.installed_version` is a CharField of this length.
VERSION_MAX_LENGTH = 20


_APP_VERSION = re.compile(r'^(\d+(?:\.\d+)*)(?:([a-z])(\d*))?$')


def _app_version_key(version: str) -> tuple | None:
    """A sortable key for an app version as the manifest allows it ('1.2.3',
    '2.0.0b1'), or None. Parts are padded ('1.0' equals '1.0.0') and a
    pre-release sorts before its release ('2.0.0b1' < '2.0.0')."""
    m = _APP_VERSION.match(version or '')
    if not m:
        return None
    parts = tuple(int(p) for p in m.group(1).split('.'))
    parts += (0,) * (8 - len(parts))
    if m.group(2):
        return (parts, 0, m.group(2), int(m.group(3) or 0))
    return (parts, 1, '', 0)


def is_newer_app_version(candidate: str, current: str) -> bool:
    """True when `candidate` is a later app version than `current`; False
    when either cannot be read."""
    a, b = _app_version_key(candidate), _app_version_key(current)
    return a is not None and b is not None and a > b


def platform_version() -> str:
    """The running Morpheus version, as settings name it ('v0.179.0')."""
    from django.conf import settings

    return str(getattr(settings, 'MORPHEUS_VERSION', '') or '')


def _within(current: tuple[int, ...], bound: tuple[int, ...]) -> int:
    """-1, 0 or 1: `current` cut to the parts `bound` names, against `bound`."""
    cut = (current + (0,) * len(bound))[: len(bound)]
    return (cut > bound) - (cut < bound)


def incompatibility(cls, version: str | None = None) -> str:
    """Why the app class `cls` cannot run on `version` (this store's by
    default), in the merchant's words, or '' when it can."""
    running = platform_version() if version is None else version
    current = parse_version(running)
    if not current:
        return ''
    label = getattr(cls, 'label', '') or cls.name
    low = getattr(cls, 'min_morpheus', '') or ''
    high = getattr(cls, 'max_morpheus', '') or ''
    if low and parse_version(low) and _within(current, parse_version(low)) < 0:
        return f'{label} needs Morpheus {low} or newer, and this store runs {running}.'
    if high and parse_version(high) and _within(current, parse_version(high)) > 0:
        return f'{label} runs on Morpheus up to {high}, and this store runs {running}.'
    return ''


def run_upgrades(registry=None) -> list[str]:
    """Record the version of every app that is on, and run each moved app's
    `on_upgrade(previous)` once. Returns the names whose step ran.

    Boot writes a row for every app it finds; on a fresh database it found no
    table, so the apps that start on get theirs here, as the next boot would
    write them, and this first deploy records them. An app that starts off waits
    for boot to write its row. Apps run in dependency order. Fail-soft: a
    database that cannot answer, or an app whose step raises, never stops the
    migrate that called this.
    """
    from django.db import DEFAULT_DB_ALIAS, DatabaseError, transaction

    from plugins.models import PluginConfig

    if registry is None:
        from plugins.registry import app_registry as registry

    # From the primary, where the compare-and-swap writes: a lagging replica
    # would show an old version, or no row at all, and the step would wait a
    # whole deploy.
    rows = PluginConfig.objects.using(DEFAULT_DB_ALIAS)
    try:
        recorded = dict(rows.values_list('plugin_name', 'installed_version'))
        active = list(registry.active_plugins())
        missing = [
            PluginConfig(plugin_name=plugin.name, is_enabled=True)
            for plugin in active
            if plugin.name not in recorded and getattr(plugin, 'enabled_by_default', True)
        ]
        if missing:
            rows.bulk_create(missing, ignore_conflicts=True)
            recorded = dict(rows.values_list('plugin_name', 'installed_version'))
    except DatabaseError:
        logger.warning('plugins: could not read the recorded app versions', exc_info=True)
        return []

    upgraded: list[str] = []
    for plugin in active:
        name, current = plugin.name, str(plugin.version)
        if name not in recorded:
            continue
        previous = recorded[name] or ''
        if previous == current:
            continue
        if len(current) > VERSION_MAX_LENGTH:
            logger.warning('plugins: %s version %r is too long to record', name, current)
            continue
        try:
            with transaction.atomic():
                # Compare-and-swap, in the step's own transaction: the row
                # holds the new version only once the step has committed.
                moved = rows.filter(plugin_name=name, installed_version=previous).update(
                    installed_version=current
                )
                runs = bool(moved) and (not previous or is_newer_app_version(current, previous))
                if runs:
                    plugin.on_upgrade(previous)
        except Exception:  # noqa: BLE001 — one app's step never stops the deploy
            logger.error(
                'plugins: %s upgrade from %r to %s failed; it runs again on the next deploy',
                name,
                previous,
                current,
                exc_info=True,
            )
            continue
        if not moved:
            continue
        if not runs:
            # A release put back (or a version nobody can compare): recorded,
            # nothing run, so moving forward again runs the step again.
            logger.info('plugins: %s recorded at %s (was %s)', name, current, previous)
            continue
        upgraded.append(name)
    if upgraded:
        logger.info('plugins: upgrade steps ran for %s', ', '.join(upgraded))
    return upgraded


def after_migrate(sender, using=None, **kwargs) -> None:
    """`post_migrate` receiver for the `plugins` app: once per migrate."""
    from django.db import DEFAULT_DB_ALIAS

    if (using or DEFAULT_DB_ALIAS) != DEFAULT_DB_ALIAS:
        return
    run_upgrades()
