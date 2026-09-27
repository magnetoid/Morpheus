"""Releasing an order's reservation must happen once, however often it is cancelled.

`Order.cancel` is an FSM transition with ``source='*'``, so an order that is
already cancelled can be cancelled again — the dashboard bulk action does
exactly that to every selected row, and GraphQL ``cancelOrder`` is documented
as "from any status". Each transition fires ``ORDER_CANCELLED``, and inventory
answered every one of them by subtracting the order's quantities from
``reserved_quantity`` again. ``reserve_for_order`` and ``commit_for_order`` are
idempotent on the order number; ``release_reservation`` was not, so the second
release ate units another, still-pending order was holding — the shelf then
advertised stock that was already promised, and the next buyer oversold it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.services import CartService, OrderService

_ADDR = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 St',
    'city': 'Town',
    'postal_code': '11000',
    'country': 'US',
}


class ReleaseReservationIdempotencyTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Widget', slug='widget-rel', sku='REL-1', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='REL-V1', price=Money(Decimal('10.00'), 'USD')
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.level = StockLevel.objects.create(
            variant=self.variant, warehouse=wh, quantity=10, reserved_quantity=0
        )

    def _place(self, session_key, qty):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(
            cart, str(self.product.id), quantity=qty, variant_id=str(self.variant.id)
        )
        return OrderService.create_from_cart(cart, f'{session_key}@example.com', _ADDR, _ADDR)

    def _reserved(self):
        self.level.refresh_from_db()
        return self.level.reserved_quantity

    def test_recancelling_an_order_keeps_another_orders_hold(self):
        first = self._place('rel-a', 2)
        self._place('rel-b', 3)  # still pending — its 3 units must stay held
        self.assertEqual(self._reserved(), 5)

        first.cancel(reason='customer changed their mind')
        first.save()
        self.assertEqual(self._reserved(), 3)

        # e.g. a bulk "Cancel" over a selection that includes this order
        first.cancel(reason='Bulk cancel from dashboard')
        first.save()
        self.assertEqual(
            self._reserved(),
            3,
            'a second ORDER_CANCELLED released units the pending order still holds',
        )
