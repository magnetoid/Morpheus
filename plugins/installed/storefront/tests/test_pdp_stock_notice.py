"""The PDP's "Out of stock — notify me" panel agrees with the inventory app.

The view decided stock with its own query — "some variant has a StockLevel row
with quantity > 0" — while `inventory.product_availability` (which the cart,
the Open Graph tags and the JSON-LD offer all follow) treats a product with no
variants, or variants with no stock rows, as untracked and purchasable, and a
backorder variant as buyable at zero. So a simple product with the default
`track_inventory=True` rendered "Out of stock" and a notify-me form directly
under a working Add-to-cart button, while its own `<head>` said in stock; and a
variant whose every unit was reserved read as in stock because the check
ignored reservations.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse

_NOTICE = '/back-in-stock/subscribe/'


class PdpStockNoticeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.warehouse = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def _product(self, slug, **kwargs):
        return Product.objects.create(
            name=slug.replace('-', ' ').title(),
            slug=slug,
            sku=slug.upper(),
            status='active',
            price=Money(Decimal('10.00'), 'USD'),
            **kwargs,
        )

    def _variant(self, product, *, stock=None, reserved=0, policy='deny'):
        variant = ProductVariant.objects.create(
            product=product, name='Default', sku=f'{product.sku}-V', inventory_policy=policy
        )
        if stock is not None:
            StockLevel.objects.create(
                variant=variant,
                warehouse=self.warehouse,
                quantity=stock,
                reserved_quantity=reserved,
            )
        return variant

    def _shows_notice(self, product) -> bool:
        response = self.client.get(f'/products/{product.slug}/')
        self.assertEqual(response.status_code, 200)
        return _NOTICE in response.content.decode()

    def test_a_product_without_variants_is_not_out_of_stock(self):
        self.assertFalse(self._shows_notice(self._product('no-variants-probe')))

    def test_a_variant_without_stock_rows_is_untracked_not_empty(self):
        product = self._product('untracked-variant-probe')
        self._variant(product)
        self.assertFalse(self._shows_notice(product))

    def test_a_backorder_variant_is_still_buyable(self):
        product = self._product('backorder-probe')
        self._variant(product, stock=0, policy='continue')
        self.assertFalse(self._shows_notice(product))

    def test_a_sold_out_variant_shows_the_notice(self):
        product = self._product('sold-out-probe')
        self._variant(product, stock=0)
        self.assertTrue(self._shows_notice(product))

    def test_fully_reserved_stock_is_sold_out(self):
        product = self._product('reserved-probe')
        self._variant(product, stock=2, reserved=2)
        self.assertTrue(self._shows_notice(product))

    def test_stock_on_hand_hides_the_notice(self):
        product = self._product('in-stock-probe')
        self._variant(product, stock=3)
        self.assertFalse(self._shows_notice(product))
