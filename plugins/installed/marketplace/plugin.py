"""Multivendor marketplace plugin manifest."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin

logger = logging.getLogger('morpheus.marketplace')


class MarketplacePlugin(Plugin):
    name = 'marketplace'
    label = 'Marketplace'
    version = '0.1.0'
    description = 'Multivendor marketplace: vendor onboarding, vendor orders, payouts.'
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        self.register_graphql_extension('plugins.installed.marketplace.graphql.queries')
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)

    def on_order_placed(self, order, **kwargs):
        try:
            from plugins.installed.marketplace.services import split_order
            split_order(order)
        except Exception as e:  # noqa: BLE001 — never block order placement
            logger.warning('marketplace: split_order failed for %s: %s', order.id, e, exc_info=True)

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage
        return [
            DashboardPage(
                label='Vendors', slug='vendors',
                view='plugins.installed.marketplace.dashboard.vendors_list',
                icon='store', section='marketplace', order=10,
            ),
            DashboardPage(
                label='Vendor orders', slug='orders',
                view='plugins.installed.marketplace.dashboard.vendor_orders',
                icon='shopping-bag', section='marketplace', order=20,
            ),
            DashboardPage(
                label='Payouts', slug='payouts',
                view='plugins.installed.marketplace.dashboard.payouts',
                icon='wallet', section='marketplace', order=30,
            ),
        ]
