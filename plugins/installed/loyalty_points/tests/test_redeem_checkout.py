"""Loyalty-points redemption at checkout — the money path.

The discount *math* already rides CART_CALCULATE_BREAKDOWN (covered by
test_redeem.py). These tests cover the wiring that actually moves points:

  * order-time debit — the ledger is debited when the order is created,
  * idempotency — a retried checkout never double-debits,
  * reversal — points come back when the order is cancelled,

exercised both at the helper level and through the real
``create_from_cart`` / ``order.cancel()`` paths, plus the cart-side
apply/remove endpoints that stash the shopper's chosen spend.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.inventory.models import StockLevel, Warehouse
from plugins.installed.loyalty_points.models import PointsTransaction
from plugins.installed.loyalty_points.services import get_balance
from plugins.installed.loyalty_points.services_redeem import (
    redeem_points_for_order,
    reverse_redemption_for_order,
)
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService, OrderService

User = get_user_model()

_ADDR = {
    'first_name': 'Mara',
    'last_name': 'H',
    'line1': '1 Main',
    'city': 'NYC',
    'state': 'NY',
    'postal_code': '10001',
    'country': 'US',
}


def _grant(customer, points):
    """Give a customer a starting balance (an earn row)."""
    PointsTransaction.objects.create(customer=customer, points=points, reason='earn_order')


class LoyaltyDebitLedgerTests(TestCase):
    """The idempotent debit / reversal helpers, in isolation."""

    def setUp(self):
        self.user = User.objects.create_user(username='reader', email='r@example.com', password='x')
        _grant(self.user, 1000)

    def _order(self):
        return Order.objects.create(
            customer=self.user,
            email=self.user.email,
            subtotal=Money(50, 'USD'),
            total=Money(50, 'USD'),
        )

    def test_debit_writes_one_negative_txn(self):
        order = self._order()
        redeem_points_for_order(self.user, 300, order=order)
        self.assertEqual(get_balance(self.user), 700)
        self.assertEqual(
            PointsTransaction.objects.filter(
                customer=self.user, reason='spend_order', order_number=order.order_number
            ).count(),
            1,
        )

    def test_debit_is_idempotent(self):
        order = self._order()
        redeem_points_for_order(self.user, 300, order=order)
        redeem_points_for_order(self.user, 300, order=order)  # a retried checkout
        self.assertEqual(get_balance(self.user), 700)  # not 400
        self.assertEqual(
            PointsTransaction.objects.filter(
                reason='spend_order', order_number=order.order_number
            ).count(),
            1,
        )

    def test_reversal_credits_back(self):
        order = self._order()
        redeem_points_for_order(self.user, 300, order=order)
        reverse_redemption_for_order(order)
        self.assertEqual(get_balance(self.user), 1000)

    def test_reversal_is_idempotent(self):
        order = self._order()
        redeem_points_for_order(self.user, 300, order=order)
        reverse_redemption_for_order(order)
        reverse_redemption_for_order(order)  # cancel + refund both fire
        self.assertEqual(get_balance(self.user), 1000)  # not 1300
        self.assertEqual(
            PointsTransaction.objects.filter(
                reason='adjust', order_number=order.order_number
            ).count(),
            1,
        )

    def test_reversal_noop_when_nothing_spent(self):
        order = self._order()
        self.assertIsNone(reverse_redemption_for_order(order))
        self.assertEqual(get_balance(self.user), 1000)


class LoyaltyCheckoutIntegrationTests(TestCase):
    """The real checkout path debits, and cancel reverses."""

    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='b@example.com', password='x')
        _grant(self.user, 1000)
        self.product = Product.objects.create(
            name='Test Book', slug='tb', sku='TB1', price=Money(20, 'USD'), status='active'
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='HC', sku='TB1-HC', price=Money(20, 'USD')
        )
        wh = Warehouse.objects.create(name='Main', code='MAIN', is_default=True)
        StockLevel.objects.create(
            variant=self.variant, warehouse=wh, quantity=10, reserved_quantity=0
        )

    def _cart_with_points(self, redeem):
        cart = CartService.get_or_create_cart(customer=self.user)
        CartService.add_item(
            cart, str(self.product.id), quantity=2, variant_id=str(self.variant.id)
        )
        cart.metadata = {**(cart.metadata or {}), 'loyalty_points_redeem': redeem}
        cart.save(update_fields=['metadata'])
        return cart

    def test_checkout_with_points_debits_ledger(self):
        cart = self._cart_with_points(300)
        order = OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address=_ADDR, billing_address=_ADDR
        )
        # 300 pts at rate 100 = $3.00 off a $40 order.
        self.assertEqual(order.total.amount, Decimal('37'))
        self.assertEqual(get_balance(self.user), 700)
        self.assertTrue(
            PointsTransaction.objects.filter(
                customer=self.user, reason='spend_order', order_number=order.order_number
            ).exists()
        )

    def test_checkout_without_points_leaves_balance(self):
        cart = CartService.get_or_create_cart(customer=self.user)
        CartService.add_item(
            cart, str(self.product.id), quantity=1, variant_id=str(self.variant.id)
        )
        OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address=_ADDR, billing_address=_ADDR
        )
        self.assertEqual(get_balance(self.user), 1000)  # untouched

    def test_cancel_reverses_points(self):
        cart = self._cart_with_points(300)
        order = OrderService.create_from_cart(
            cart=cart, email='b@example.com', shipping_address=_ADDR, billing_address=_ADDR
        )
        self.assertEqual(get_balance(self.user), 700)
        # cancel fires ORDER_CANCELLED → loyalty reversal subscriber
        fresh = Order.objects.get(pk=order.pk)
        fresh.cancel(reason='test')
        fresh.save()
        self.assertEqual(get_balance(self.user), 1000)


class LoyaltyApplyEndpointTests(TestCase):
    """The /checkout/points/apply|remove/ endpoints (owned by the plugin)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='shopper', email='s@example.com', password='pw'
        )
        _grant(self.user, 1000)

    def _cart_key(self):
        cart = CartService.get_or_create_cart(customer=self.user)
        return (cart.metadata or {}).get('loyalty_points_redeem')

    def test_apply_requires_auth(self):
        resp = self.client.post('/checkout/points/apply/', {'points': '300'})
        self.assertIn(resp.status_code, (302, 403))
        self.assertFalse(self._cart_key())  # anonymous never mutates a cart

    def test_apply_sets_clamped_metadata(self):
        self.client.force_login(self.user)
        self.client.post('/checkout/points/apply/', {'points': '300'})
        self.assertEqual(self._cart_key(), 300)

    def test_apply_clamps_to_balance(self):
        self.client.force_login(self.user)
        self.client.post('/checkout/points/apply/', {'points': '99999'})
        self.assertEqual(self._cart_key(), 1000)  # capped at the 1000-pt balance

    def test_remove_clears(self):
        self.client.force_login(self.user)
        self.client.post('/checkout/points/apply/', {'points': '300'})
        self.client.post('/checkout/points/remove/')
        self.assertFalse(self._cart_key())
