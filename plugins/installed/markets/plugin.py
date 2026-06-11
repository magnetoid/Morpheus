"""markets plugin manifest."""

from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin

logger = logging.getLogger('morpheus.markets')


class MarketsPlugin(Plugin):
    name = 'markets'
    label = 'Markets'
    version = '0.1.0'
    description = (
        'Per-country pricing, currency, and locale. Resolves a market '
        "from the visitor's country (Cloudflare CF-IPCountry header by "
        'default) and applies optional per-product price overrides.'
    )
    has_models = True

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.markets.urls',
            prefix='dashboard/markets/',
            namespace='markets',
        )

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Markets',
                section='settings',
                icon='globe',
                view='plugins.installed.markets.views.index',
                order=15,
                nav='settings',
            ),
        ]
