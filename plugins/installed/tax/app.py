"""Tax plugin manifest."""

from __future__ import annotations

import logging

from morpheus.app import DashboardPage, Plugin

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
        from morpheus.core import events  # noqa: PLC0415

        # CART_CALCULATE_TOTAL is deprecated — the canonical event is
        # CART_CALCULATE_BREAKDOWN, fired from OrderService since 2026-04.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=20)
        self.register_urls(
            'plugins.installed.tax.urls_dashboard',
            prefix='dashboard/tax/',
            namespace='tax_dashboard',
        )

    def on_cart_breakdown(self, value, cart=None, address=None, **kwargs):
        if cart is None or not isinstance(value, dict):
            return value
        try:
            from plugins.installed.tax.services import compute_tax_for_cart  # noqa: PLC0415

            result = compute_tax_for_cart(
                cart,
                country=(address or {}).get('country', ''),
                region=(address or {}).get('region', ''),
            )
            tax_total = result.get('total')
            value['tax'] = tax_total

            subtotal = value.get('subtotal')
            shipping = value.get('shipping')
            discount = value.get('discount')
            currency = str(value.get('currency') or getattr(subtotal, 'currency', 'USD'))
            from decimal import Decimal  # noqa: I001,PLC0415
            from djmoney.money import Money  # noqa: PLC0415

            subtotal_a = Decimal(str(getattr(subtotal, 'amount', 0) or 0))
            shipping_a = Decimal(str(getattr(shipping, 'amount', 0) or 0))
            tax_a = Decimal(str(getattr(tax_total, 'amount', 0) or 0))
            discount_a = Decimal(str(getattr(discount, 'amount', 0) or 0))
            total_a = subtotal_a + shipping_a + tax_a - discount_a
            if total_a < 0:
                total_a = Decimal('0')
            value['total'] = Money(total_a.quantize(Decimal('0.01')), currency)
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('tax: on_cart_breakdown failed: %s', e, exc_info=True)
            return value

    def on_cart_total(self, value, cart=None, address=None, **kwargs):
        """Cart total filter: add tax based on shipping address (or default region).

        `value` is a Money for the running total. `address` is a dict with
        country/region keys, supplied by the checkout flow. We return a new
        Money with tax added.
        """
        if cart is None:
            return value
        try:
            from plugins.installed.tax.services import compute_tax_for_cart  # noqa: PLC0415

            country = (address or {}).get('country', '') if address else ''
            region = (address or {}).get('region', '') if address else ''
            result = compute_tax_for_cart(cart, country=country, region=region)
            return value + result.get('total')
        except Exception as e:  # noqa: BLE001
            logger.warning('tax: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.tax.agent_tools import (  # noqa: PLC0415
            list_rates_tool,
            set_rate_tool,
        )

        return [list_rates_tool, set_rate_tool]

    def contribute_dashboard_pages(self) -> list:
        # Regions + rates are one 'Tax' page now (the template stacks both
        # sections); a single settings nav entry instead of two. Both views/URLs
        # stay intact — `rates` redirects to the unified page (ADR 0003).
        return [
            DashboardPage(
                label='Tax',
                slug='regions',
                view='plugins.installed.tax.dashboard.regions',
                icon='percent',
                section='taxes',
                order=10,
                nav='settings',
                url='/dashboard/tax/regions/',
            ),
        ]

    # No SettingsPanel: tax config (provider / inclusive pricing / default
    # region) lives on the TaxConfiguration model and is edited in the
    # "Tax calculation" section of the unified Tax page (dashboard.regions).
    # The old panel wrote to plugin-config — a key nothing read — so it was a
    # no-op AND a duplicate "Taxes" settings entry. Removed per ADR 0003.
