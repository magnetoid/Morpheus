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

from morpheus.app import DashboardPage, Plugin, StorefrontBlock

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
        # Expose translations over GraphQL (mirrors the generic i18n MCP tools)
        # so external translators + tools can read/write translations by API.
        self.register_graphql_extension('plugins.installed.localization.graphql.queries')
        self.register_graphql_extension('plugins.installed.localization.graphql.mutations')

    def contribute_storefront_blocks(self) -> list:
        # Language switcher — renders only when >1 language is routable
        # (settings.LANGUAGES). Sits in the footer; POSTs to set_language which
        # redirects to the language-prefixed URL.
        return [
            StorefrontBlock(
                slot='footer_extra',
                template='localization/blocks/language_switcher.html',
                priority=40,
            )
        ]

    def contribute_dashboard_pages(self) -> list:
        # Two tool cards on Settings › General: what the storefront says in
        # each language, and which languages it is offered in.
        return [
            DashboardPage(
                label='Translations & languages',
                slug='translations',
                view='plugins.installed.localization.views.translations_index',
                icon='languages',
                section='general',
                order=20,
                nav='settings',
                hint='Translate the storefront and its content',
            ),
            DashboardPage(
                label='Languages',
                slug='languages',
                view='plugins.installed.localization.views.languages_index',
                icon='globe',
                section='general',
                order=21,
                nav='settings',
                hint='The languages the storefront is offered in',
            ),
        ]
