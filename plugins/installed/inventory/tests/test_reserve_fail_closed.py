"""``reserve_for_order`` must fail CLOSED when it cannot confirm a reservation.

It runs under ``ORDER_RESERVE_STOCK``, which orders fires with
``raise_errors=True`` (orders/services.py:602) precisely so an unconfirmable
reservation aborts the order. Until v0.36 a ``DatabaseError`` inside the
per-allocation transaction was logged and the loop simply *continued*: the
function returned normally, checkout believed stock was held, and the order
shipped against inventory nobody reserved — a silent oversell on any DB hiccup.

Tested through the real checkout path rather than a stubbed order, so the
assertion is the one that matters: no order, no reservation.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService

_ADDR = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 St',
    'city': 'Town',
    'postal_code': '11000',
    'country': 'US',
}


class ReserveFailsClosedTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Widget', slug='widget', sku='PRD-W', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='W-1', price=Money(Decimal('10.00'), 'USD')
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.level = StockLevel.objects.create(
            variant=self.variant, warehouse=wh, quantity=10, reserved_quantity=0
        )

    def _checkout(self, session_key):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        return OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)

    def test_db_error_during_reserve_aborts_checkout_instead_of_overselling(self):
        before = Order.objects.count()
        with (
            patch.object(StockLevel, 'save', side_effect=DatabaseError('connection lost')),
            self.assertRaises(Exception),  # noqa: B017 — any propagated failure is fine
        ):
            self._checkout('s-failclosed')

        # The order must not exist and no stock may be held: previously the
        # error was swallowed, the order was created, and reserved stayed 0.
        self.assertEqual(Order.objects.count(), before)
        self.level.refresh_from_db()
        self.assertEqual(self.level.reserved_quantity, 0)

    def test_healthy_checkout_still_reserves(self):
        self._checkout('s-healthy')
        self.level.refresh_from_db()
        self.assertEqual(self.level.reserved_quantity, 2)
