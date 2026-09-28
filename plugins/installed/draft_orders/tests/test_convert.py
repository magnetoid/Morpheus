"""Converting a draft runs the steps every other order gets.

``convert_to_order`` created the Order directly, so a draft-converted sale had
no stock reservation, no ORDER_PLACED (no confirmation email, fraud check,
affiliate or CRM attribution), and two clicks made two orders. It keeps the
staff-entered prices — a draft is a quote — but now reserves stock (refusing a
short one), fires ORDER_PLACED, and converts once.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.draft_orders import services
from plugins.installed.draft_orders.models import DraftOrder, DraftOrderLine
from plugins.installed.orders.models import Order


class DraftConversionTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Quoted Book', slug='quoted-book', sku='Q-1',
            price=Money(Decimal('20.00'), 'USD'), status='active',
        )  # fmt: skip
        self.variant = ProductVariant.objects.create(
            product=product, name='Hardback', sku='Q-1-H', price=Money(Decimal('20.00'), 'USD')
        )
        self.draft = DraftOrder.objects.create(customer_email='buyer@example.com')
        DraftOrderLine.objects.create(
            draft=self.draft, variant=self.variant, product_name='Quoted Book', sku='Q-1-H',
            unit_price=Money(Decimal('15.00'), 'USD'), quantity=2,
        )  # fmt: skip
        services.recalc(self.draft)
        self.placed = []

        def handler(order=None, **kwargs):
            self.placed.append(order.pk)

        hook_registry.register(MorpheusEvents.ORDER_PLACED, handler, plugin=None)
        self.addCleanup(hook_registry.unregister, MorpheusEvents.ORDER_PLACED, handler)

    def test_converting_places_the_order_once_at_the_quoted_price(self):
        order = services.convert_to_order(self.draft)
        again = services.convert_to_order(DraftOrder.objects.get(pk=self.draft.pk))
        self.assertEqual(again.pk, order.pk)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(self.placed, [order.pk])
        self.assertEqual(order.total.amount, Decimal('30.00'))

    def test_short_stock_refuses_the_conversion(self):
        from plugins.installed.inventory.models import StockLevel, Warehouse

        warehouse = Warehouse.objects.create(name='Main', code='MAIN')
        StockLevel.objects.create(variant=self.variant, warehouse=warehouse, quantity=1)
        with self.assertRaises(Exception):  # noqa: B017 — InsufficientStockError
            services.convert_to_order(self.draft)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(DraftOrder.objects.get(pk=self.draft.pk).status, self.draft.status)
        self.assertEqual(self.placed, [])
