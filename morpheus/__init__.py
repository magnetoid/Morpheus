"""Morpheus — public framework API.

Plugin authors import from `morpheus`; they should never need to reach
into Django, the registry internals, or the `core/`/`plugins/` packages
directly. Django is the runtime; `morpheus` is the framework.

Quickstart::

    # plugins/installed/hello/plugin.py
    from morpheus import Plugin, DashboardPage, events

    class HelloPlugin(Plugin):
        name = 'hello'
        label = 'Hello World'
        version = '0.1.0'

        def ready(self) -> None:
            self.register_hook(events.ORDER_PLACED, self.on_order)

        def contribute_dashboard_pages(self):
            return [DashboardPage(
                label='Hello',
                slug='hello',
                view='plugins.installed.hello.views.index',
                icon='heart',
            )]

        def on_order(self, order, **kw):
            ...

Submodules
----------
* ``morpheus.events``     — catalogue of built-in hook event names.
* ``morpheus.models``     — re-exports of Django ORM + ``MoneyField``.
* ``morpheus.forms``      — re-exports of Django form primitives.
* ``morpheus.views``      — view decorators (``staff_required``, …).
* ``morpheus.hooks``      — direct access to the global hook registry
  for plugins that need to fire events from outside ``ready()``.
"""
from __future__ import annotations

# Re-export the plugin base under a clean public name.
from plugins.base import MorpheusPlugin as Plugin
from plugins.base import PluginConfigurationError
from plugins.contributions import (
    DashboardPage,
    SettingsPanel,
    StorefrontBlock,
)

# `events` and `hooks` are exposed as submodules (see morpheus/events.py
# and morpheus/hooks.py) — importing them here would create a cycle.

__all__ = [
    'Plugin',
    'PluginConfigurationError',
    'DashboardPage',
    'SettingsPanel',
    'StorefrontBlock',
    '__version__',
]

__version__ = '0.1.0'
