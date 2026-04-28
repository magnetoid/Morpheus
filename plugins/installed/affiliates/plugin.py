"""Affiliates plugin manifest."""
from __future__ import annotations

from morpheus import events
from morpheus import Plugin


class AffiliatesPlugin(Plugin):
    name = 'affiliates'
    label = 'Affiliate Platform'
    version = '0.1.0'
    description = 'Affiliate links, attribution, conversions, payouts.'
    has_models = True
    requires = ['orders', 'customers']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.affiliates.graphql.queries')
        self.register_urls('plugins.installed.affiliates.urls', prefix='', namespace='affiliates')
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=70)

    def on_order_placed(self, order, **kwargs):
        """If the order carries an affiliate code on its source/metadata, attribute it."""
        code = ''
        # Storefront writes the code into staff_notes or shipping_address.affiliate_code
        if getattr(order, 'shipping_address', None):
            code = order.shipping_address.get('affiliate_code', '') if isinstance(order.shipping_address, dict) else ''
        if not code and getattr(order, 'source', '').startswith('affiliate:'):
            code = order.source.split(':', 1)[1]
        if not code:
            return
        from plugins.installed.affiliates.services import attribute_order
        attribute_order(order=order, affiliate_code=code)

    def contribute_agent_tools(self) -> list:
        from plugins.installed.affiliates.agent_tools import (
            create_affiliate_tool, list_affiliates_tool,
            mark_payout_paid_tool, pending_payouts_tool,
        )
        return [
            list_affiliates_tool, pending_payouts_tool,
            mark_payout_paid_tool, create_affiliate_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage
        return [
            DashboardPage(
                label='Affiliates', slug='list',
                view='plugins.installed.affiliates.dashboard.affiliates_list',
                icon='link', section='growth', order=10,
            ),
            DashboardPage(
                label='Payouts', slug='payouts',
                view='plugins.installed.affiliates.dashboard.payouts_list',
                icon='wallet', section='growth', order=20,
            ),
        ]
