"""metafields plugin manifest."""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.metafields')


class MetafieldsPlugin(Plugin):
    name = 'metafields'
    label = 'Metafields'
    version = '0.1.0'
    description = (
        'Schema-less custom fields on any record — products, customers, '
        'orders, pages, anything. Same idea as Shopify metafields but '
        "works on every Morpheus model out of the box via Django's "
        'GenericForeignKey.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.metafields.urls',
            prefix='dashboard/metafields/',
            namespace='metafields',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Metafields',
                section='developer',
                icon='braces',
                view='plugins.installed.metafields.views.index',
                order=30,
                nav='settings',
            ),
        ]
