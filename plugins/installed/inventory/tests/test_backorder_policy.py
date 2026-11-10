"""What checkout counts (v0.152.0), through the real checkout path.

* A variant that keeps selling at 0 (``inventory_policy='continue'``) takes what
  is free and the order's timeline names the shortfall; until v0.152.0 the
  reservation refused it like any other, so "backorders" did nothing.
* A product whose tracking is switched off is never counted, whatever rows it has.
* A cart line that names no variant counts the stock of its product's one
  variant (the default variant a product sold in one form gets).
* A variant with no stock row is not counted, at checkout or in the cart hold.
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.catalog.variants import ensure_stock_variant
from plugins.installed.inventory import cart_reservations
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.inventory.services import InsufficientStockError, InventoryService
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


class CheckoutCountsTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Lamp', slug='lamp', sku='LAMP', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Std', sku='LAMP-1', price=Money(Decimal('10'), 'USD')
        )
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def _checkout(self, qty, *, variant=True, key='s1'):
        cart = CartService.get_or_create_cart(session_key=key)
        CartService.add_item(
            cart,
            str(self.product.id),
            quantity=qty,
            variant_id=str(self.variant.id) if variant else None,
        )
        return OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)

    def _level(self):
        return StockLevel.objects.get(variant=self.variant, warehouse=self.main)

    def test_a_short_variant_without_backorders_is_refused(self):
        InventoryService.set_quantity(self.variant, self.main, 1)
        with self.assertRaises(InsufficientStockError):
            self._checkout(3)
        self.assertFalse(Order.objects.exists())

    def test_a_backordered_variant_sells_past_zero_and_says_so(self):
        self.variant.inventory_policy = 'continue'
        self.variant.save()
        InventoryService.set_quantity(self.variant, self.main, 1)
        order = self._checkout(3)
        self.assertEqual(self._level().reserved_quantity, 1)
        note = order.events.get(event_type='backordered').message
        self.assertIn('2× LAMP-1', note)

    def test_a_product_that_does_not_count_stock_is_never_refused(self):
        self.product.track_inventory = False
        self.product.save()
        InventoryService.set_quantity(self.variant, self.main, 0)
        self._checkout(5)
        self.assertEqual(self._level().reserved_quantity, 0)

    def test_a_variant_with_no_stock_row_is_not_counted(self):
        self._checkout(5)
        self.assertFalse(StockLevel.objects.exists())

    def test_a_line_without_a_variant_counts_the_products_one_variant(self):
        InventoryService.set_quantity(self.variant, self.main, 4)
        self._checkout(3, variant=False)
        self.assertEqual(self._level().reserved_quantity, 3)


class DefaultVariantCheckoutTests(TestCase):
    def test_stock_entered_on_a_one_form_product_holds_at_checkout(self):
        product = Product.objects.create(
            name='Mug', slug='mug', sku='MUG', status='active', price=8
        )
        main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        variant = ensure_stock_variant(product)
        InventoryService.set_quantity(variant, main, 2)
        cart = CartService.get_or_create_cart(session_key='mug')
        CartService.add_item(cart, str(product.id), quantity=3)
        with self.assertRaises(InsufficientStockError):
            OrderService.create_from_cart(cart, 'buyer@example.com', _ADDR, _ADDR)


class CartHoldTrackedTests(TestCase):
    """The cart hold caps only what the order's reservation would cap."""

    def setUp(self):
        self.product = Product.objects.create(
            name='Kettle', slug='kettle', sku='KET', status='active', price=10
        )
        self.variant = ProductVariant.objects.create(product=self.product, name='Std', sku='KET-1')
        self.main = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)

    def test_only_a_counted_variant_is_capped(self):
        vid = str(self.variant.pk)
        self.assertFalse(cart_reservations._is_tracked(vid))  # no stock row
        InventoryService.set_quantity(self.variant, self.main, 2)
        self.assertTrue(cart_reservations._is_tracked(vid))
        self.variant.inventory_policy = 'continue'
        self.variant.save()
        self.assertFalse(cart_reservations._is_tracked(vid))
        self.variant.inventory_policy = 'deny'
        self.variant.save()
        self.product.track_inventory = False
        self.product.save()
        self.assertFalse(cart_reservations._is_tracked(vid))

    def test_a_switched_off_warehouse_is_not_free_stock(self):
        InventoryService.set_quantity(self.variant, self.main, 5)
        self.assertEqual(cart_reservations._absolute_available(str(self.variant.pk)), 5)
        self.main.is_active = False
        self.main.save()
        self.assertEqual(cart_reservations._absolute_available(str(self.variant.pk)), 0)
