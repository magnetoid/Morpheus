"""Orders count the orders a restore would lose (RESTORE_LOSSES)."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from core import restore
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


class OrdersLostTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Widget', slug='widget-r3', sku='R3-W', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='R3-WV', price=Money(Decimal('10.00'), 'USD')
        )
        warehouse = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        StockLevel.objects.create(
            variant=self.variant, warehouse=warehouse, quantity=10, reserved_quantity=0
        )

    def _place(self, session_key):
        cart = CartService.get_or_create_cart(session_key=session_key)
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        return OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)

    def test_orders_placed_since_the_backup_are_counted(self):
        since = timezone.now()
        old = self._place('s-old')
        Order.objects.filter(pk=old.pk).update(placed_at=since - timezone.timedelta(hours=2))
        self._place('s-new')
        rows = {row['label']: row['count'] for row in restore.losses(since)}
        self.assertEqual(rows['orders placed'], 1)
