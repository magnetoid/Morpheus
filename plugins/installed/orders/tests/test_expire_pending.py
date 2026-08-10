"""Unpaid pending orders must release their stock.

Checkout reserves stock through the fail-closed ``ORDER_RESERVE_STOCK`` gate,
and inventory releases it on ``ORDER_CANCELLED``. Nothing ever cancelled an
order that was created and never paid, though: a failed card only marks the
transaction FAILED, and an abandoned redirect leaves the order ``pending``
forever. Its units stayed reserved permanently, so available stock shrank with
every abandoned checkout until the merchant appeared oversold on stock they
still had. ``orders/tasks.py`` was a 0-byte file.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService
from plugins.installed.orders.tasks import expire_pending_orders

_ADDR = {
    'first_name': 'A',
    'last_name': 'B',
    'address_line_1': '1 St',
    'city': 'Town',
    'postal_code': '11000',
    'country': 'US',
}


class ExpirePendingOrdersTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Widget', slug='widget-exp', sku='EXP-1', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='EXP-V1', price=Money(Decimal('10.00'), 'USD')
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.level = StockLevel.objects.create(
            variant=self.variant, warehouse=wh, quantity=10, reserved_quantity=0
        )

    def _place(self, session_key='s-exp'):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        return OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)

    def _age(self, order, minutes):
        Order.objects.filter(pk=order.pk).update(
            placed_at=timezone.now() - timezone.timedelta(minutes=minutes)
        )

    def _reserved(self):
        self.level.refresh_from_db()
        return self.level.reserved_quantity

    def test_stale_unpaid_order_is_cancelled_and_stock_released(self):
        order = self._place()
        self.assertEqual(self._reserved(), 2)

        self._age(order, 120)
        self.assertEqual(expire_pending_orders(), 1)

        # `status` is a protected FSMField — refresh_from_db() cannot set it.
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'cancelled')
        # ORDER_CANCELLED fired -> inventory released the reservation.
        self.assertEqual(self._reserved(), 0)

    def test_recent_order_is_left_alone(self):
        self._place()
        self.assertEqual(expire_pending_orders(), 0)
        self.assertEqual(self._reserved(), 2)

    def test_paid_order_is_never_cancelled(self):
        order = self._place()
        Order.objects.filter(pk=order.pk).update(payment_status='paid')
        self._age(order, 120)

        self.assertEqual(expire_pending_orders(), 0)
        self.assertEqual(Order.objects.get(pk=order.pk).status, 'pending')

    def test_zero_minutes_disables_the_sweep(self):
        from plugins.registry import plugin_registry

        order = self._place()
        self._age(order, 10_000)

        plugin = plugin_registry.get('orders')
        original = plugin.get_config_value('pending_order_expiry_minutes', 60)
        plugin.set_config('pending_order_expiry_minutes', 0)
        try:
            self.assertEqual(expire_pending_orders(), 0)
        finally:
            plugin.set_config('pending_order_expiry_minutes', original)

        self.assertEqual(Order.objects.get(pk=order.pk).status, 'pending')

    def test_sweep_is_idempotent(self):
        order = self._place()
        self._age(order, 120)
        self.assertEqual(expire_pending_orders(), 1)
        # Already cancelled -> no longer a candidate.
        self.assertEqual(expire_pending_orders(), 0)
