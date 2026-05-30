"""Shipping plugin manifest."""

from __future__ import annotations

import logging

from morpheus import Plugin, SettingsPanel

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
        from morpheus import events  # noqa: PLC0415

        self.register_graphql_extension('plugins.installed.shipping.graphql.queries')
        # Tax must run BEFORE shipping (so shipping doesn't get taxed unless
        # we explicitly want that). Tax uses priority 20; we use 30.
        # CART_CALCULATE_TOTAL is deprecated — the canonical event is
        # CART_CALCULATE_BREAKDOWN, fired from OrderService since 2026-04.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=30)
        self.register_urls(
            'plugins.installed.shipping.urls_dashboard',
            prefix='dashboard/shipping/',
            namespace='shipping_dashboard',
        )

    def on_cart_breakdown(self, value, cart=None, address=None, shipping_rate_id=None, **kwargs):
        if cart is None or not isinstance(value, dict):
            return value
        if not shipping_rate_id:
            return value
        try:
            meta = value.get('meta') or {}
            free_shipping = bool(meta.get('free_shipping'))

            from plugins.installed.shipping.services import quote_rate  # noqa: PLC0415

            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            quote = quote_rate(cart=cart, rate_id=shipping_rate_id, country=country, region=region)
            if not quote:
                return value

            amount = quote.get('amount')
            if free_shipping:
                from decimal import Decimal  # noqa: PLC0415

                from djmoney.money import Money  # noqa: PLC0415

                currency = str(
                    value.get('currency') or getattr(value.get('subtotal'), 'currency', 'USD')
                )
                amount = Money(Decimal('0'), currency)

            if amount is not None:
                value['shipping'] = amount
                meta['shipping_rate_name'] = quote.get('name') or ''
                value['meta'] = meta

            subtotal = value.get('subtotal')
            shipping = value.get('shipping')
            tax = value.get('tax')
            discount = value.get('discount')
            currency = str(value.get('currency') or getattr(subtotal, 'currency', 'USD'))
            from decimal import Decimal  # noqa: PLC0415

            from djmoney.money import Money  # noqa: PLC0415

            subtotal_a = Decimal(str(getattr(subtotal, 'amount', 0) or 0))
            shipping_a = Decimal(str(getattr(shipping, 'amount', 0) or 0))
            tax_a = Decimal(str(getattr(tax, 'amount', 0) or 0))
            discount_a = Decimal(str(getattr(discount, 'amount', 0) or 0))
            total_a = subtotal_a + shipping_a + tax_a - discount_a
            if total_a < 0:
                total_a = Decimal('0')
            value['total'] = Money(total_a.quantize(Decimal('0.01')), currency)

            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('shipping: on_cart_breakdown failed: %s', e, exc_info=True)
            return value

    def on_cart_total(self, value, cart=None, address=None, shipping_rate_id=None, **kwargs):
        """Add the chosen shipping rate's amount to the cart total."""
        if cart is None or not shipping_rate_id:
            return value
        try:
            from plugins.installed.shipping.services import quote_rate  # noqa: PLC0415

            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            quote = quote_rate(
                cart=cart,
                rate_id=shipping_rate_id,
                country=country,
                region=region,
            )
            if quote and quote['amount']:
                return value + quote['amount']
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('shipping: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.shipping.agent_tools import (  # noqa: PLC0415
            add_flat_rate_tool,
            list_zones_tool,
        )

        return [list_zones_tool, add_flat_rate_tool]

    def contribute_dashboard_pages(self) -> list:
        from morpheus import DashboardPage  # noqa: PLC0415

        return [
            DashboardPage(
                label='Shipping zones',
                slug='zones',
                view='plugins.installed.shipping.dashboard.zones',
                icon='map',
                section='shipping',
                order=10,
                nav='settings',
                url='/dashboard/shipping/zones/',
            ),
            DashboardPage(
                label='Shipping rates',
                slug='rates',
                view='plugins.installed.shipping.dashboard.rates',
                icon='truck',
                section='shipping',
                order=20,
                nav='settings',
                url='/dashboard/shipping/rates/',
            ),
        ]

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
                    'type': 'boolean',
                    'default': False,
                    'title': 'Apply tax to shipping cost',
                },
                # ── Carrier credentials ────────────────────────────
                # Used by carrier_shippo / carrier_easypost rate types.
                # Origin address is supplied as JSON so it can hold
                # the full {name, street1, city, state, zip, country}
                # shape both adapters expect.
                'shippo_api_key': {
                    'type': 'string',
                    'default': '',
                    'title': 'Shippo · API key',
                    'description': 'Live rates + label printing via goshippo.com. '
                    'ShippoToken from your dashboard.',
                },
                'shippo_default_address': {
                    'type': 'object',
                    'default': {},
                    'title': 'Shippo · Origin address',
                    'description': 'Where parcels ship from. JSON object with '
                    'street1, city, state, zip, country.',
                },
                'easypost_api_key': {
                    'type': 'string',
                    'default': '',
                    'title': 'EasyPost · API key',
                    'description': 'Live rates + labels via easypost.com.',
                },
                'easypost_default_address': {
                    'type': 'object',
                    'default': {},
                    'title': 'EasyPost · Origin address',
                    'description': 'Falls back to Shippo origin if blank.',
                },
            },
        }
