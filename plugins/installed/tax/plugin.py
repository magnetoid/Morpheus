"""Tax plugin manifest."""
from __future__ import annotations

import logging

from morpheus import Plugin
from morpheus import DashboardPage, SettingsPanel

logger = logging.getLogger('morpheus.tax')


class TaxPlugin(Plugin):
    name = 'tax'
    label = 'Tax'
    version = '1.0.0'
    description = (
        'Tax engine: regions, categorised rates (VAT, US sales tax, EU OSS), '
        'cart-total hook integration, Stripe Tax adapter ready.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        from morpheus import events
        self.register_hook(events.CART_CALCULATE_TOTAL, self.on_cart_total, priority=20)

    def on_cart_total(self, value, cart=None, address=None, **kwargs):
        """Cart total filter: add tax based on shipping address (or default region).

        `value` is a Money for the running total. `address` is a dict with
        country/region keys, supplied by the checkout flow. We return a new
        Money with tax added.
        """
        if cart is None:
            return value
        try:
            from plugins.installed.tax.services import compute_tax_for_cart
            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            result = compute_tax_for_cart(cart, country=country, region=region)
            tax_total = result.get('total')
            if tax_total is None:
                return value
            return value + tax_total
        except Exception as e:  # noqa: BLE001
            logger.warning('tax: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.tax.agent_tools import list_rates_tool, set_rate_tool
        return [list_rates_tool, set_rate_tool]

    def contribute_dashboard_pages(self) -> list:
        return []  # admin via Django admin for now

    def contribute_settings_panel(self) -> SettingsPanel:
        return SettingsPanel(
            label='Tax',
            description='Configure tax provider, rounding, and inclusive pricing.',
            schema=self.get_config_schema(),
        )

    def get_config_schema(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'provider': {'type': 'string', 'enum': ['local', 'stripe', 'none'], 'default': 'local'},
                'prices_include_tax': {'type': 'boolean', 'default': False},
            },
        }
