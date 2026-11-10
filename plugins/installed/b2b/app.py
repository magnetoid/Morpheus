"""B2B plugin manifest."""

from __future__ import annotations

from morpheus.app import DashboardPage, Plugin
from morpheus.core import events


class B2bPlugin(Plugin):
    name = 'b2b'
    label = 'B2B'
    version = '1.0.0'
    description = (
        'B2B commerce: quotes, per-account price lists, net-N payment terms. '
        'Reuses crm.Account; adds Quote/QuoteLine + PriceList + '
        'NetTermsAgreement models.'
    )
    has_models = True
    requires = ['catalog', 'orders', 'crm']

    def ready(self) -> None:
        self.register_hook(events.DASHBOARD_SEARCH, self.on_dashboard_search)
        self.register_urls(
            'plugins.installed.b2b.urls_dashboard',
            prefix='dashboard/b2b/',
            namespace='b2b_dashboard',
        )
        # Storefront-facing routes (bulk CSV reorder uploader).
        self.register_urls(
            'plugins.installed.b2b.urls',
            prefix='b2b/',
            namespace='b2b',
        )

    def on_dashboard_search(self, value, query='', words=None, **kwargs):
        """Price lists (by name) in the dashboard's search box."""
        from plugins import dashboard_search as ds
        from plugins.installed.b2b.models import PriceList

        return ds.add(
            value,
            PriceList,
            query,
            words,
            fields=('name', 'description'),
            section='Price lists',
            kind='price_list',
            icon='tags',
            capability='b2b.write',
            label=lambda p: p.name,
            hint=lambda p: 'Price list',
            url=lambda p: f'/dashboard/b2b/pricelists/{p.pk}/',
        )

    def contribute_agent_tools(self) -> list:
        from plugins.installed.b2b.agent_tools import (  # noqa: PLC0415
            list_quotes_tool,
            set_net_terms_tool,
        )

        return [list_quotes_tool, set_net_terms_tool]

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Price lists',
                slug='pricelists',
                view='plugins.installed.b2b.dashboard.pricelists',
                icon='tag',
                section='products',
                order=70,
            ),
        ]
