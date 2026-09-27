"""Bulk CSV reorder must charge what the catalog charges.

`/b2b/bulk-order/` writes CartItems with a unit price of its own choosing, so
anything it gets wrong is billed at checkout as-is.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.b2b.services_bulk_order import apply_to_cart
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.customers.models import Customer
from plugins.installed.orders.models import Cart, CartItem


class BulkOrderVariantPricingTests(TestCase):
    def setUp(self):
        # A variable product: the dashboard form defaults the parent price to 0
        # because each variant carries its own price.
        self.product = Product.objects.create(
            name='Atlas',
            slug='atlas-b2b',
            sku='ATLAS',
            product_type='variable',
            price=Money(Decimal('0'), 'USD'),
            status='active',
        )
        self.hardcover = ProductVariant.objects.create(
            product=self.product,
            name='Hardcover',
            sku='ATLAS-HC',
            price=Money(Decimal('30.00'), 'USD'),
        )
        self.customer = Customer.objects.create_user(
            email='buyer@b2b.example', username='b2b-buyer', password='x'
        )
        self.cart = Cart.objects.create(customer=self.customer)

    def test_variant_sku_is_priced_at_the_variant_price(self):
        apply_to_cart(cart=self.cart, parsed_rows=[(1, 'ATLAS-HC', 2)], account=None)

        line = CartItem.objects.get(cart=self.cart, variant=self.hardcover)
        # Used to be the PARENT price (0.00 here) — a free hardcover.
        self.assertEqual(line.unit_price, Money(Decimal('30.00'), 'USD'))

    def test_variant_without_its_own_price_falls_back_to_the_product(self):
        self.product.price = Money(Decimal('18.00'), 'USD')
        self.product.save(update_fields=['price'])
        paperback = ProductVariant.objects.create(
            product=self.product, name='Paperback', sku='ATLAS-PB', price=None
        )

        apply_to_cart(cart=self.cart, parsed_rows=[(1, 'ATLAS-PB', 1)], account=None)

        line = CartItem.objects.get(cart=self.cart, variant=paperback)
        self.assertEqual(line.unit_price, Money(Decimal('18.00'), 'USD'))
