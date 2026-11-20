"""Releasing an order's reservation must happen once, however often it is cancelled.

Until v0.180.0 ``Order.cancel`` was an FSM transition with ``source='*'``, so an
order that was already cancelled could be cancelled again — the dashboard bulk
action did exactly that to every selected row, and GraphQL ``cancelOrder`` was
documented as "from any status". Each transition fired ``ORDER_CANCELLED``, and
inventory answered every one of them by subtracting the order's quantities from
``reserved_quantity`` again. The FSM now refuses a second cancel, and the event
can still arrive twice (a retried hook), so the release stays idempotent. ``reserve_for_order`` and ``commit_for_order`` are
idempotent on the order number; ``release_reservation`` was not, so the second
release ate units another, still-pending order was holding — the shelf then
advertised stock that was already promised, and the next buyer oversold it.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django_fsm import TransitionNotAllowed
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
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

        # A second cancel is refused now; the event arriving again must still
        # leave the pending order's hold alone.
        with self.assertRaises(TransitionNotAllowed):
            first.cancel(reason='Bulk cancel from dashboard')
        hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=Order.objects.get(pk=first.pk))
        self.assertEqual(
            self._reserved(),
            3,
            'a second ORDER_CANCELLED released units the pending order still holds',
        )
