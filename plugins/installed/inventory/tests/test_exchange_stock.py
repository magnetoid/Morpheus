"""A free exchange order takes its unit off the shelf (C4, v0.188.0).

It fires no ORDER_PAID, which is what turns a reservation into a sale, so the
return's close commits it instead."""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.exchange import ExchangeLine
from plugins.installed.orders.models import Order, OrderItem
from plugins.installed.orders.refunds import ReturnRequest, ReturnService


def _usd(n):
    return Money(n, 'USD')


class ExchangeStockTests(TestCase):
    def setUp(self):
        book = Product.objects.create(
            name='Zephyr Atlas', slug='zephyr-atlas-x', sku='ZAX', price=10, status='active'
        )
        paperback = ProductVariant.objects.create(
            product=book, name='Paperback', sku='ZAX-PB', price=_usd(10)
        )
        self.hardback = ProductVariant.objects.create(
            product=book, name='Hardback', sku='ZAX-HB', price=_usd(10)
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.level = StockLevel.objects.create(
            variant=self.hardback, warehouse=wh, quantity=5, reserved_quantity=0
        )
        order = Order.objects.create(
            email='q@example.com',
            subtotal=_usd(10),
            total=_usd(10),
            payment_status='paid',
            payment_gateway='manual',
        )
        item = OrderItem.objects.create(
            order=order,
            product=book,
            variant=paperback,
            product_name='Zephyr Atlas',
            quantity=1,
            unit_price=_usd(10),
            total_price=_usd(10),
        )
        self.rr = ReturnRequest.objects.create(
            order=order, state='approved', items=[{'order_item_id': str(item.pk), 'quantity': 1}]
        )
        self.lines = [ExchangeLine(order_item_id=str(item.pk), variant_id=str(self.hardback.pk))]

    def test_free_exchange_turns_its_reservation_into_a_sale(self):
        ReturnService.close(self.rr, outcome='exchange', exchange=self.lines)
        self.level.refresh_from_db()
        self.assertEqual((self.level.quantity, self.level.reserved_quantity), (4, 0))

    def test_charged_exchange_keeps_its_reservation_until_paid(self):
        ReturnService.close(self.rr, outcome='exchange', exchange=self.lines, fee=_usd(5))
        self.level.refresh_from_db()
        self.assertEqual((self.level.quantity, self.level.reserved_quantity), (5, 1))
