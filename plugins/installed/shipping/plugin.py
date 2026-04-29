"""Shipping plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin
from morpheus import SettingsPanel

logger = logging.getLogger('morpheus.shipping')


class ShippingPlugin(Plugin):
    name = 'shipping'
    label = 'Shipping'
    version = '1.0.0'
    description = (
        'Shipping zones + rates: flat fee, weight tiers, order-total tiers, '
        'free over threshold, plus stub adapters for Shippo / EasyPost.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        from morpheus import events
        # Tax must run BEFORE shipping (so shipping doesn't get taxed unless
        # we explicitly want that). Tax uses priority 20; we use 30.
        self.register_hook(events.CART_CALCULATE_TOTAL, self.on_cart_total, priority=30)

    def on_cart_total(self, value, cart=None, address=None, shipping_rate_id=None, **kwargs):
        """Add the chosen shipping rate's amount to the cart total."""
        if cart is None or not shipping_rate_id:
            return value
        try:
            from plugins.installed.shipping.services import quote_rate
            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            quote = quote_rate(
                cart=cart, rate_id=shipping_rate_id, country=country, region=region,
            )
            if quote and quote['amount']:
                return value + quote['amount']
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('shipping: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.shipping.agent_tools import (
            add_flat_rate_tool, list_zones_tool,
        )
        return [list_zones_tool, add_flat_rate_tool]

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Shipping',
            description='Manage shipping zones, rates, free-shipping rules.',
            schema=self.get_config_schema(),
            category='shipping',
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'tax_shipping': {
                    'type': 'boolean', 'default': False,
                    'title': 'Apply tax to shipping cost',
                },
            },
        }
