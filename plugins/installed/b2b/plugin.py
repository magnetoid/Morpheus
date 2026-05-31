"""B2B plugin manifest."""

from __future__ import annotations

from morpheus import DashboardPage, Plugin


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
                section='b2b',
                order=10,
            ),
        ]
