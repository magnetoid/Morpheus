"""Switching an app on or off: the one writer every surface goes through.

The dashboard's Apps page, Linda's `plugins.toggle` / `plugins.enable` /
`plugins.disable` and `manage.py morpheus enable|disable` all call
`set_enabled`. It decides whether the switch may move (the app exists, what it
needs is on, nothing it conflicts with is on, nothing that needs it is on, and
the store can run without it), then flips it through the registry's persisted
pair. That stores the switch and bumps the token every other web worker and
Celery worker follows on its next request or task (`AppRegistry.reconcile`),
so the change reaches the whole store without a restart.

Before this, each surface wrote `PluginConfig` itself and only the process that
took the click changed: the other workers kept the old set until a restart, and
Linda's tools changed no process at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger('morpheus.plugins')


class AppSwitchRefused(Exception):
    """The switch may not move. The message says why, in the merchant's words."""


@dataclass(frozen=True)
class AppSwitch:
    name: str
    label: str
    enabled: bool
    changed: bool


def set_enabled(name: str, enabled: bool, actor: Any = None) -> AppSwitch:
    """Switch the app `name` on or off for the whole store.

    `actor` is who asked (a user, or a label such as ``'linda'``), for the
    audit log. Raises `AppSwitchRefused` and changes nothing when the switch
    may not move.
    """
    from plugins.registry import app_registry

    if name not in app_registry._classes:
        raise AppSwitchRefused(f'There is no app named {name!r}.')
    stored = app_registry._stored_switches()
    if stored is None:
        raise AppSwitchRefused("The store's database did not answer, so nothing changed.")
    switches = _Switches(app_registry, stored)
    was_on = switches.is_on(name)
    refusal = switches.why_not_on(name) if enabled else switches.why_not_off(name)
    if refusal:
        raise AppSwitchRefused(refusal)
    from django.db import DatabaseError

    try:
        if enabled:
            if not app_registry.activate(name):
                raise AppSwitchRefused(
                    f'{switches.label(name)} could not start, so it stays off. '
                    'The error log has the details.'
                )
        else:
            # The tear-down follows the store's switch, not this worker: it still
            # runs when the app's start-up failed here.
            app_registry.deactivate(name, tear_down=was_on)
    except DatabaseError as e:
        logger.error('plugins: could not store the switch for %s: %s', name, e, exc_info=True)
        raise AppSwitchRefused(
            f"The store's database did not save the switch for {switches.label(name)}, "
            'so nothing changed.'
        ) from e

    changed = was_on != bool(enabled)
    if changed:
        from core.audit.services import record

        record(
            event_type='app.enabled' if enabled else 'app.disabled',
            actor=actor,
            target=name,
        )
    logger.info(
        'plugins: %s switched %s by %s', name, 'on' if enabled else 'off', actor or 'unknown'
    )
    return AppSwitch(name=name, label=switches.label(name), enabled=bool(enabled), changed=changed)


class _Switches:
    """The stored switches, with each app's manifest, for deciding a change."""

    def __init__(self, registry, stored: dict[str, bool]) -> None:
        self.registry = registry
        self.classes = registry._classes
        self.stored = stored

    def label(self, app: str) -> str:
        return getattr(self.classes.get(app), 'label', '') or app

    def is_on(self, app: str) -> bool:
        if app not in self.classes:
            return False
        return self.stored.get(app, self.registry.is_active(app))

    def why_not_on(self, name: str) -> str:
        cls = self.classes[name]
        for dep in cls.requires:
            if dep.startswith('core.'):
                continue  # a core Django app, always installed
            if dep not in self.classes:
                return f'{self.label(name)} needs {dep}, which this store does not have.'
            if not self.is_on(dep):
                return f'{self.label(name)} needs {self.label(dep)}; switch that on first.'
        for other, other_cls in sorted(self.classes.items()):
            if other == name or not self.is_on(other):
                continue
            if other in cls.conflicts or name in other_cls.conflicts:
                return (
                    f'{self.label(name)} cannot run beside {self.label(other)}; '
                    'switch that off first.'
                )
        return ''

    def why_not_off(self, name: str) -> str:
        from core.safety import protection_reason

        reason = protection_reason(name)
        if reason:
            return f'{self.label(name)} cannot be switched off: {reason}.'
        if getattr(self.classes[name], 'system', False):
            return f'{self.label(name)} is part of the platform and cannot be switched off.'
        needing = [
            self.label(other)
            for other, other_cls in sorted(self.classes.items())
            if other != name and name in other_cls.requires and self.is_on(other)
        ]
        if not needing:
            return ''
        one = len(needing) == 1
        return (
            f'{", ".join(needing)} {"needs" if one else "need"} {self.label(name)}; '
            f'switch {"it" if one else "them"} off first.'
        )
