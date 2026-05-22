"""Localization plugin — merchant-facing surface over core.i18n.

The translation kernel ([`core/i18n/`](../../../core/i18n/)) already provides:
  - `Translation` generic-FK row model
  - `{{ obj|trans:"field" }}` template filter
  - agent tools for machine translation
  - service helpers for resolve/lookup/cache

What this plugin adds:
  - A dashboard page at /dashboard/apps/localization/translations/ that
    lists translatable objects + lets a merchant edit translations
    inline.
  - A "Languages" settings page where the merchant picks which target
    languages the store should ship to.
  - A storefront block contribution that emits hreflang alternates for
    each enabled language.

This is intentionally THIN — all the heavy lifting (DB schema, fallback
chain, agent-driven auto-translation) lives in core.i18n. The plugin is
purely the merchant-facing surface.
"""
from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.localization')


class LocalizationPlugin(Plugin):
    name = 'localization'
    label = 'Localization'
    version = '1.0.0'
    description = (
        'Merchant-facing surface over the core.i18n translation kernel. '
        'Edit translations inline, pick target languages, emit hreflang '
        'alternates from the storefront.'
    )
    has_models = False
    requires = ['catalog']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.localization.urls',
            prefix='dashboard/apps/localization/',
            namespace='localization',
        )

    def contribute_dashboard_pages(self) -> list:
        # One combined entry in the *settings* sidebar — translations +
        # languages are the same admin concern (the localization
        # control room). The Languages URL still works directly; we
        # just don't list it separately in the rail.
        return [
            DashboardPage(
                label='Translations & languages',
                slug='translations',
                view='plugins.installed.localization.views.translations_index',
                icon='languages',
                section='settings',
                order=20,
                nav='settings',
            ),
            DashboardPage(
                label='Languages',
                slug='languages',
                view='plugins.installed.localization.views.languages_index',
                icon='globe',
                section='settings',
                order=21,
                nav='hidden',
            ),
        ]
