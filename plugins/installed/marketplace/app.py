"""Multivendor marketplace plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import Plugin, SettingsPanel, StorefrontBlock
from morpheus.core import events

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
        self.register_urls(
            'plugins.installed.marketplace.urls_dashboard',
            prefix='dashboard/marketplace/',
            namespace='marketplace_dashboard',
        )
        self.register_hook(events.ORDER_PLACED, self.on_order_placed, priority=80)
        # Contribute the Vendor on/off panel to the dashboard customer-detail
        # page. Only registered while marketplace is enabled, so disabling the
        # plugin removes the toggle (modular-os contract).
        from plugins.installed.marketplace.customer_panel import vendor_panel  # noqa: PLC0415

        self.register_hook(events.CUSTOMER_DETAIL_PANELS, vendor_panel, priority=30)

    def contribute_storefront_blocks(self) -> list:
        # Account-page tile linking the signed-in vendor to their dashboard
        # (/vendor/me/). Renders only when the user has a Vendor row;
        # disabling the plugin removes the tile.
        return [
            StorefrontBlock(
                slot='account_nav',
                template='marketplace/blocks/account_tile.html',
                priority=30,
                context_keys=['request'],
            ),
        ]

    def on_order_placed(self, order, **kwargs):
        try:
            from plugins.installed.marketplace.services import split_order  # noqa: PLC0415

            split_order(order)
        except Exception as e:  # noqa: BLE001 — never block order placement
            logger.warning('marketplace: split_order failed for %s: %s', order.id, e, exc_info=True)

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Marketplace',
            description='Default commission rates and approval policy for new vendors.',
            schema=self.get_config_schema(),
            category='payments',
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
                'min_payout_threshold': {
                    'type': 'number',
                    'title': 'Minimum payout threshold',
                    'description': 'A vendor must accrue at least this much before a payout is generated.',
                    'default': 50,
                },
            },
        }

    def contribute_dashboard_pages(self) -> list:
        from morpheus.app import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Vendors',
                slug='vendors',
                view='plugins.installed.marketplace.dashboard.vendors_list',
                icon='store',
                section='vendors',
                order=10,
            ),
            DashboardPage(
                label='Applications',
                slug='applications',
                view='plugins.installed.marketplace.dashboard.applications_list',
                icon='inbox',
                section='vendors',
                order=15,
            ),
            DashboardPage(
                label='Vendor orders',
                slug='orders',
                view='plugins.installed.marketplace.dashboard.vendor_orders',
                icon='shopping-bag',
                section='vendors',
                order=20,
            ),
            DashboardPage(
                label='Payouts',
                slug='payouts',
                view='plugins.installed.marketplace.dashboard.payouts',
                icon='wallet',
                section='vendors',
                order=30,
            ),
            DashboardPage(
                label='Payout accounts',
                slug='payout-accounts',
                view='plugins.installed.marketplace.dashboard.payout_accounts',
                icon='credit-card',
                section='vendors',
                order=35,
            ),
            DashboardPage(
                label='Reports',
                slug='reports',
                view='plugins.installed.marketplace.dashboard.reports',
                icon='bar-chart-3',
                section='vendors',
                order=40,
            ),
        ]
