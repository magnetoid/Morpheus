"""The nightly cart check prices a product that is for sale, not a pre-launch preview.

Irving runs with "pre-launch products are not for sale" on, and its first active
product is such a preview. The check picked it, the cart refused it, and every
night's health email said "A cart can be priced: failed" about a store doing
exactly what it was told (found by the first errors_report, 2026-10-11).
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.health import cart_pricing_check


class CartCheckPrelaunchTests(TestCase):
    def setUp(self):
        from plugins.registry import app_registry

        self.orders = app_registry.get('orders')
        self.addCleanup(self.orders.invalidate_config_cache)
        self.orders.set_config('prelaunch_noindex_not_for_sale', True)
        Product.objects.create(
            name='Aa preview kit', slug='aa-preview', sku='PRE-1', status='active',
            price=Money(Decimal('25.00'), 'USD'), noindex=True,
        )  # fmt: skip

    def test_a_preview_is_skipped_for_a_product_on_sale(self):
        Product.objects.create(
            name='Water carrier', slug='water-carrier', sku='RDY-1', status='active',
            price=Money(Decimal('12.00'), 'USD'),
        )  # fmt: skip
        result = cart_pricing_check()
        self.assertTrue(result['ok'], result)

    def test_nothing_on_sale_yet_is_not_a_failure(self):
        result = cart_pricing_check()
        self.assertTrue(result['ok'], result)
        self.assertIn('pre-launch', result['detail'])
