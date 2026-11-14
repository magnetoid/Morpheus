"""Localization — the work of translating a store's content.

Settings → General → Translations shows, per language the store is offered in and
per kind of content (from `TRANSLATABLE_CONTENT`), how much is translated, what
waits for review and what is missing; an editor puts the source beside its
translation; AI drafts wait for review (`drafting.py`, `tasks.py`). The storefront
shows a reviewed translation once an object is fully translated (`core.i18n`), and
this app adds the footer language switcher.
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
        'Translate the store: how much of each language is done, an editor beside '
        'the source, AI drafts to review, and the footer language switcher.'
    )
    has_models = False
    # paginate_and_sort and the dashboard shell's templates.
    requires = ['catalog', 'admin_dashboard']

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
            ),
            # The bar that offers the page in the visitor's language; the block
            # renders nothing unless the setting is on and the store has 2+ languages.
            StorefrontBlock(
                slot='global_head',
                template='localization/blocks/language_bar.html',
                priority=60,
            ),
        ]

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'suggest_language': {
                    'type': 'boolean',
                    'default': False,
                    'title': "Offer a page in the visitor's language",
                },
            },
        }

    def contribute_agent_tools(self) -> list:
        from plugins.installed.localization.agent_tools import (  # noqa: PLC0415
            draft_translations_tool,
        )

        return [draft_translations_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Translations',
                slug='translations',
                view='plugins.installed.localization.views.translations_index',
                icon='languages',
                section='general',
                order=20,
                nav='settings',
                hint="Translate the store's content into its other languages",
            ),
        ]
