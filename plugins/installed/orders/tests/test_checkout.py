"""End-to-end checkout tests: cart → order → email → inventory."""

from __future__ import annotations

from decimal import Decimal
from unittest import skipIf

from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, StockMovement, Warehouse
from plugins.installed.inventory.services import InventoryService
from plugins.installed.orders.services import CartService, OrderService

_IS_SQLITE = connection.vendor == 'sqlite'


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='shop@example.com',
    STORE_NAME='Test Shop',
    STORE_URL='https://shop.example',
)
class CheckoutFlowTests(TestCase):
    def setUp(self) -> None:
        self.product = Product.objects.create(
            name='Test Book',
            slug='test-book',
            sku='TB1',
            price=Money(20, 'USD'),
            status='active',
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name='Hardcover',
            sku='TB1-HC',
            price=Money(20, 'USD'),
        )
        self.warehouse = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        self.stock = StockLevel.objects.create(
            variant=self.variant,
            warehouse=self.warehouse,
            quantity=10,
            reserved_quantity=0,
        )

    def test_add_to_cart_creates_cart_and_item(self):
        cart = CartService.get_or_create_cart(session_key='s-1')
        item = CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        self.assertEqual(item.quantity, 2)
        self.assertEqual(cart.items.count(), 1)
        self.assertEqual(cart.subtotal, Decimal('40'))

    def test_create_from_cart_emits_order_and_clears_cart(self):
        cart = CartService.get_or_create_cart(session_key='s-2')
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(
            cart=cart,
            email='buyer@example.com',
            shipping_address={
                'first_name': 'Mara',
                'last_name': 'H',
                'line1': '1 Main',
                'city': 'NYC',
                'state': 'NY',
                'postal_code': '10001',
                'country': 'US',
            },
            billing_address={
                'first_name': 'Mara',
                'last_name': 'H',
                'line1': '1 Main',
                'city': 'NYC',
                'state': 'NY',
                'postal_code': '10001',
                'country': 'US',
            },
        )
        self.assertEqual(order.email, 'buyer@example.com')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total.amount, Decimal('40'))
        self.assertEqual(cart.items.count(), 0)

    def test_create_from_cart_stamps_visitor_id_into_metadata(self):
        # Anonymous attribution: experiments' ORDER_PLACED handler reads
        # metadata['visitor_id'] to credit `v:` assignments.
        addr = {'first_name': 'V', 'last_name': 'H', 'line1': '1 Main', 'country': 'US'}
        cart = CartService.get_or_create_cart(session_key='s-vis')
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(cart, 'v@example.com', addr, addr, visitor_id='vc1')
        self.assertEqual(order.metadata.get('visitor_id'), 'vc1')

        cart2 = CartService.get_or_create_cart(session_key='s-vis2')
        CartService.add_item(
            cart2, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        order2 = OrderService.create_from_cart(cart2, 'v2@example.com', addr, addr)
        # No cookie → no visitor stamp (other subscribers, e.g. fraud_rules,
        # may add their own metadata keys after placement).
        self.assertNotIn('visitor_id', order2.metadata)

    def test_order_placement_reserves_stock(self):
        cart = CartService.get_or_create_cart(session_key='s-3')
        CartService.add_item(
            cart, str(self.product.id), quantity=3, variant_id=str(self.variant.id)
        )
        OrderService.create_from_cart(
            cart=cart,
            email='b@example.com',
            shipping_address={},
            billing_address={},
        )
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 3)
        self.assertEqual(self.stock.quantity, 10)  # not yet committed

    def test_reservation_is_idempotent(self):
        cart = CartService.get_or_create_cart(session_key='s-4')
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address={}, billing_address={}
        )
        # Re-running reserve should be a no-op
        before = StockMovement.objects.filter(
            movement_type='reserve', reference=order.order_number
        ).count()
        InventoryService.reserve_for_order(order)
        after = StockMovement.objects.filter(
            movement_type='reserve', reference=order.order_number
        ).count()
        self.assertEqual(before, after)

    def test_commit_decrements_stock_after_payment(self):
        cart = CartService.get_or_create_cart(session_key='s-5')
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address={}, billing_address={}
        )
        # Simulate payment success.
        from core.hooks import MorpheusEvents, hook_registry

        hook_registry.fire(MorpheusEvents.ORDER_PAID, order=order)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)

    def test_release_on_cancel(self):
        cart = CartService.get_or_create_cart(session_key='s-6')
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address={}, billing_address={}
        )
        InventoryService.release_reservation(order)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 0)

    def test_oversell_is_blocked_at_checkout(self):
        # The stock gate must ROLL BACK a short-stock order, not create+charge
        # it. Previously reservation fired on the plain order.placed bus, which
        # swallows the InsufficientStockError, so two shoppers could both buy the
        # last unit. Now it's a raise_errors filter inside the order transaction.
        from plugins.installed.inventory.services import InsufficientStockError
        from plugins.installed.orders.models import Order

        self.stock.quantity = 1
        self.stock.save(update_fields=['quantity'])

        c1 = CartService.get_or_create_cart(session_key='os-1')
        CartService.add_item(c1, str(self.product.id), quantity=1, variant_id=str(self.variant.id))
        OrderService.create_from_cart(
            cart=c1, email='a@example.com', shipping_address={}, billing_address={}
        )
        n_after_first = Order.objects.count()

        c2 = CartService.get_or_create_cart(session_key='os-2')
        CartService.add_item(c2, str(self.product.id), quantity=1, variant_id=str(self.variant.id))
        with self.assertRaises(InsufficientStockError):
            OrderService.create_from_cart(
                cart=c2, email='b@example.com', shipping_address={}, billing_address={}
            )
        # The second order must not exist — the gate rolled it back.
        self.assertEqual(Order.objects.count(), n_after_first)

    @skipIf(_IS_SQLITE, 'cascade delete + UUID + taggit overflows SQLite — postgres path')
    def test_order_confirmation_email_is_sent(self):
        cart = CartService.get_or_create_cart(session_key='s-7')
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        order = OrderService.create_from_cart(
            cart=cart,
            email='buyer@example.com',
            shipping_address={'first_name': 'Mara'},
            billing_address={},
        )
        # The signal in plugin.on_order_placed should have fired.
        # In tests, plugin hooks may not be wired; trigger directly to be sure.
        from plugins.installed.orders.email import send_order_confirmation

        ok = send_order_confirmation(order)
        self.assertTrue(ok)
        self.assertGreaterEqual(len(mail.outbox), 1)
        msg = mail.outbox[-1]
        self.assertIn(order.order_number, msg.subject)
        self.assertIn('Test Shop', msg.body)
        self.assertEqual(msg.to, ['buyer@example.com'])
