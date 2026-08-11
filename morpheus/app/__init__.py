"""Plugin SDK — everything needed to author a Morpheus plugin.

One of the three project SDKs (torsor ADR 0035 /
``docs/plans/sdk-restructure-2026-07.md``):

* ``morpheus.app`` — authoring a plugin (this module)
* ``morpheus.core``   — consuming the kernel (hooks, agents, audit, money)
* ``morpheus.theme``  — authoring a storefront theme

Quickstart::

    from morpheus.app import Plugin, DashboardPage, SettingsPanel
    from morpheus.app.views import render, staff_required
    from morpheus.app import models  # Django ORM + MoneyField

Additive facade: the classic ``from morpheus import Plugin`` still works — this
subpackage is the canonical door going forward, adopted incrementally per ADR 0035.
"""

from __future__ import annotations

from plugins.base import MorpheusPlugin as Plugin
from plugins.base import PluginConfigurationError
from plugins.contributions import (
    DashboardPage,
    EmailTemplateDef,
    SettingsPanel,
    StorefrontBlock,
    dashboard_trail,
)

from . import forms, models, views

__all__ = [
    'Plugin',
    'PluginConfigurationError',
    'DashboardPage',
    'EmailTemplateDef',
    'SettingsPanel',
    'StorefrontBlock',
    'dashboard_trail',
    'forms',
    'models',
    'views',
]
