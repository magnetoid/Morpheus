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
        'Tax engine: regions and rates (VAT, US sales tax, EU OSS), reduced rates '
        'for product categories, compound rates, tax on shipping and tax-inclusive '
        'prices, applied to every cart.'
    )
    has_models = True
    requires = ['catalog', 'orders']

    def ready(self) -> None:
        from morpheus.core import events  # noqa: PLC0415

        # After shipping (30) and the member discount (40), so both are in the
        # base it taxes; before the tenders (points 45, store credit 46, gift
        # card 50), which pay the total and must not lower it.
        self.register_hook(events.CART_CALCULATE_BREAKDOWN, self.on_cart_breakdown, priority=42)
        # The product form's "Tax category" card.
        self.register_hook(events.PRODUCT_FORM_CARDS, self.on_product_form_cards, priority=50)
        self.register_hook(events.PRODUCT_FORM_SAVED, self.on_product_form_saved, priority=50)
        self.register_urls(
            'plugins.installed.tax.urls_dashboard',
            prefix='dashboard/tax/',
            namespace='tax_dashboard',
        )

    def on_cart_breakdown(self, value, cart=None, address=None, **kwargs):
        if cart is None or not isinstance(value, dict):
            return value
        try:
            from decimal import Decimal  # noqa: PLC0415

            from djmoney.money import Money  # noqa: PLC0415

            from plugins.installed.tax.services import compute_tax_for_cart  # noqa: PLC0415

            result = compute_tax_for_cart(
                cart,
                country=(address or {}).get('country', ''),
                # Checkout addresses carry the subdivision as ``state``; shipping
                # reads both keys the same way.
                region=(address or {}).get('region') or (address or {}).get('state') or '',
                discount=value.get('discount'),
                shipping=value.get('shipping'),
            )
            lines = [
                {'label': line['rate_name'], 'amount': str(line['amount'].amount)}
                for line in result.get('lines') or []
            ]
            meta = value.setdefault('meta', {})
            if result.get('included'):
                # The prices already hold this tax: the shopper pays them as
                # shown, and the invoice says how much of it is tax. It stays out
                # of ``tax`` because every later handler totals
                # subtotal + shipping + tax − discount.
                meta['tax_included'] = lines
            else:
                value['tax'] = result.get('total')
                # The rates behind the total, kept on the order for its invoice
                # (orders/services.py:_order_metadata).
                meta['tax_lines'] = lines

            def amount(key):
                return Decimal(str(getattr(value.get(key), 'amount', 0) or 0))

            subtotal = value.get('subtotal')
            currency = str(value.get('currency') or getattr(subtotal, 'currency', 'USD'))
            total = amount('subtotal') + amount('shipping') + amount('tax') - amount('discount')
            value['total'] = Money(max(total, Decimal('0')).quantize(Decimal('0.01')), currency)
            return value
        except Exception as e:  # noqa: BLE001
            logger.warning('tax: on_cart_breakdown failed: %s', e, exc_info=True)
            return value

    def on_product_form_cards(self, value, product=None, **kwargs):
        """The "Tax category" card, shown once the store has a category."""
        from plugins.installed.tax.models import ProductTaxCategory, TaxCategory  # noqa: PLC0415

        categories = list(TaxCategory.objects.all())
        if not categories:
            return value
        current = ''
        if product is not None and getattr(product, 'pk', None):
            current = (
                ProductTaxCategory.objects.filter(product=product)
                .values_list('category_id', flat=True)
                .first()
                or ''
            )
        value.append(
            {
                'template': 'tax/blocks/product_form_card.html',
                'context': {'tax_categories': categories, 'tax_category': current},
                'order': 60,
            }
        )
        return value

    def on_product_form_saved(self, product=None, post=None, **kwargs):
        """Save the card's choice. A form without the card leaves the product as
        it was."""
        if product is None or post is None or 'tax_category_submitted' not in post:
            return
        from plugins.installed.tax.services import set_product_category  # noqa: PLC0415

        try:
            set_product_category(product, (post.get('tax_category') or '').strip())
        except ValueError as exc:
            logger.warning('tax: product form category not saved: %s', exc)

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
            region = (
                ((address or {}).get('region') or (address or {}).get('state') or '')
                if address
                else ''
            )
            result = compute_tax_for_cart(cart, country=country, region=region)
            return value + result.get('total')
        except Exception as e:  # noqa: BLE001
            logger.warning('tax: on_cart_total failed: %s', e, exc_info=True)
            return value

    def contribute_agent_tools(self) -> list:
        from plugins.installed.tax.agent_tools import (  # noqa: PLC0415
            list_rates_tool,
            set_category_tool,
            set_product_category_tool,
            set_rate_tool,
            update_settings_tool,
        )

        return [
            list_rates_tool,
            set_rate_tool,
            set_category_tool,
            set_product_category_tool,
            update_settings_tool,
        ]

    def contribute_dashboard_pages(self) -> list:
        # Regions + rates are one page (the template stacks both sections),
        # a tool card on Settings › Shipping & tax. Both views/URLs stay
        # intact — `rates` redirects to the unified page (ADR 0003).
        return [
            DashboardPage(
                label='Tax regions',
                slug='regions',
                view='plugins.installed.tax.dashboard.regions',
                icon='percent',
                section='shipping',
                order=10,
                nav='settings',
                url='/dashboard/tax/regions/',
                hint='Tax rates per region',
            ),
        ]

    # No SettingsPanel: tax config (provider / inclusive pricing / default
    # region) lives on the TaxConfiguration model and is edited in the
    # "Tax calculation" section of the unified Tax page (dashboard.regions).
    # The old panel wrote to plugin-config — a key nothing read — so it was a
    # no-op AND a duplicate "Taxes" settings entry. Removed per ADR 0003.
