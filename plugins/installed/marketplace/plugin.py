"""Multivendor marketplace plugin manifest."""
from __future__ import annotations

import logging

from morpheus import events
from morpheus import Plugin, SettingsPanel

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
        self.register_urls('plugins.installed.marketplace.urls', prefix='', namespace='marketplace')
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)

    def on_order_placed(self, order, **kwargs):
        try:
            from plugins.installed.marketplace.services import split_order
            split_order(order)
        except Exception as e:  # noqa: BLE001 — never block order placement
            logger.warning('marketplace: split_order failed for %s: %s', order.id, e, exc_info=True)

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Marketplace',
            description='Default commission rates and approval policy for new vendors.',
            schema=self.get_config_schema(),
            category='marketing',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'default_commission_percent': {
                    'type': 'number',
                    'title': 'Default commission %',
                    'description': "Platform commission on each vendor's gross. New vendors inherit this.",
                    'default': 15,
                },
                'auto_approve_applications': {
                    'type': 'boolean',
                    'title': 'Auto-approve applications',
                    'description': 'When on, new vendor applications are approved on submission. Useful for invite-only marketplaces.',
                    'default': False,
                },
                'min_payout_threshold': {
                    'type': 'number',
                    'title': 'Minimum payout threshold',
                    'description': 'A vendor must accrue at least this much before a payout is generated.',
                    'default': 50,
                },
                'require_tax_id': {
                    'type': 'boolean',
                    'title': 'Require tax ID on application',
                    'default': True,
                },
            },
        }

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage
        return [
            DashboardPage(
                label='Vendors', slug='vendors',
                view='plugins.installed.marketplace.dashboard.vendors_list',
                icon='store', section='marketplace', order=10,
            ),
            DashboardPage(
                label='Applications', slug='applications',
                view='plugins.installed.marketplace.dashboard.applications_list',
                icon='inbox', section='marketplace', order=15,
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
            DashboardPage(
                label='Payout accounts', slug='payout-accounts',
                view='plugins.installed.marketplace.dashboard.payout_accounts',
                icon='credit-card', section='marketplace', order=35,
            ),
            DashboardPage(
                label='Reports', slug='reports',
                view='plugins.installed.marketplace.dashboard.reports',
                icon='bar-chart-3', section='marketplace', order=40,
            ),
        ]
