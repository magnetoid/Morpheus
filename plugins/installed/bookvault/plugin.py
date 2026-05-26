"""Bookvault plugin manifest.

Mirrors the WooCommerce → Bookvault.app integration: live shipping
quotes from BV's API at checkout, auto-resend of paid orders to BV
fulfilment, per-product link tracking, and the BV-hosted bulk product
linker reachable from the admin dashboard.
"""
from __future__ import annotations

import logging

from morpheus import DashboardPage, Plugin, SettingsPanel, events

logger = logging.getLogger('morpheus.bookvault')


class BookvaultPlugin(Plugin):
    name = 'bookvault'
    label = 'Bookvault'
    version = '0.1.0'
    description = (
        'Print-on-demand book fulfilment via Bookvault.app. Live shipping '
        'quotes at checkout, auto-resend paid orders to BV, per-product '
        'link tracking, BV-hosted bulk product linker.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        self.register_urls(
            'plugins.installed.bookvault.urls',
            prefix='dashboard/apps/bookvault/',
            namespace='bookvault',
        )
        # Auto-send on order paid — matches the WP plugin's "Resend Order
        # To Bookvault" path, but proactive rather than admin-triggered.
        self.register_hook(
            events.ORDER_PAID, self.on_order_paid, priority=80,
        )

    def on_order_paid(self, order=None, **kwargs):
        if order is None:
            return
        try:
            from plugins.installed.bookvault.services import send_order
            send_order(order=order)
        except Exception as e:  # noqa: BLE001 — never break checkout if BV is down
            logger.warning('bookvault: auto-send order=%s failed: %s',
                           getattr(order, 'id', '?'), e, exc_info=True)

    def contribute_dashboard_pages(self) -> list:
        return [
            DashboardPage(
                label='Bookvault', slug='overview',
                view='plugins.installed.bookvault.views.overview',
                icon='book-open', section='shipping', order=20,
                nav='main',
                url='/dashboard/apps/bookvault/',
            ),
        ]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Bookvault',
            description=(
                'Print-on-demand credentials + behaviour. Token is minted '
                'by hitting auth.bookvault.app with this store\'s URL.'
            ),
            schema=self.get_config_schema(),
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'token': {
                    'type': 'string', 'default': '',
                    'title': 'BV client token',
                    'description': 'Minted by auth.bookvault.app/api/WooAuth. Click "Connect" on the overview page rather than pasting here.',
                },
                'store_id': {
                    'type': 'string', 'default': '',
                    'title': 'BV store ID',
                },
                'authenticated': {
                    'type': 'boolean', 'default': False,
                    'title': 'Authenticated',
                    'description': 'True once auth.bookvault.app has acknowledged this store.',
                },
                'auto_send_on_paid': {
                    'type': 'boolean', 'default': True,
                    'title': 'Auto-send orders on payment',
                    'description': 'When on, every ORDER_PAID hook forwards the order to BV fulfilment. Off = admin must Resend manually.',
                },
                'use_live_shipping_rates': {
                    'type': 'boolean', 'default': True,
                    'title': 'Live shipping rates at checkout',
                    'description': 'Quote BV\'s shipping API for any cart containing a 13-digit-SKU (ISBN) line.',
                },
            },
        }
