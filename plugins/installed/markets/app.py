"""markets plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events

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
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_urls(
            'plugins.installed.markets.urls',
            prefix='dashboard/markets/',
            namespace='markets',
        )

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Markets (by code, name or currency) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.markets.models import Market

        return ds.add(
            value,
            Market,
            query,
            words,
            fields=('code', 'label', 'currency'),
            section='Markets',
            kind='market',
            icon='globe',
            label=lambda m: m.label or m.code,
            hint=lambda m: f'Market · {m.code} · {m.currency}',
            url=lambda m: f'/dashboard/markets/{m.pk}/',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.markets.agent_tools import markets_list_tool  # noqa: PLC0415

        return [markets_list_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                slug='index',
                label='Markets',
                section='general',
                icon='globe',
                view='plugins.installed.markets.views.index',
                order=15,
                nav='settings',
                hint='Countries, currencies and prices per market',
            ),
        ]
