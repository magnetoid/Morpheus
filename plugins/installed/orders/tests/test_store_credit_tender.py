"""Store credit can be spent at checkout, and comes back when the order does.

Returns issued store credit and the account page showed the balance, but no
cart step could spend it. It is now a tender like a gift card (after loyalty,
before gift cards), debited when the order is placed, and re-credited in full
on cancel and pro rata on a refund — each exactly once.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from djmoney.money import Money

from morpheus.core import MorpheusEvents, hook_registry
from plugins.installed.catalog.models import Product
from plugins.installed.orders import store_credit
from plugins.installed.orders.models import Refund
from plugins.installed.orders.services import CartService, OrderService

ADDRESS = {'country': 'US'}


class StoreCreditTenderTests(TestCase):
    def setUp(self):
        self.customer = get_user_model().objects.create_user(
            username='credit', email='credit@example.com', password='x'
        )
        self.product = Product.objects.create(
            name='Credit Book', slug='credit-book', sku='SC-1',
            price=Money(Decimal('20.00'), 'USD'), status='active',
        )  # fmt: skip
        self.cart = CartService.get_or_create_cart(customer=self.customer)
        CartService.add_item(cart=self.cart, product_id=str(self.product.id))
        store_credit.issue(self.customer, amount=Money(Decimal('10.00'), 'USD'), reference='RMA-1')

    def _balance(self):
        return store_credit.available_for(self.customer, 'USD')

    def _order(self):
        return OrderService.create_from_cart(self.cart, 'credit@example.com', ADDRESS, ADDRESS)

    def test_checkout_spends_the_credit(self):
        breakdown = OrderService.calculate_cart_breakdown(cart=self.cart, address=ADDRESS)
        self.assertEqual(breakdown['total'].amount, Decimal('10.00'))
        order = self._order()
        self.assertEqual(order.total.amount, Decimal('10.00'))
        self.assertEqual(self._balance(), Decimal('0'))

    def test_cancelling_returns_the_credit_once(self):
        order = self._order()
        order.cancel()
        order.save()
        hook_registry.fire(MorpheusEvents.ORDER_CANCELLED, order=order)  # a second delivery
        self.assertEqual(self._balance(), Decimal('10.00'))

    def test_a_refund_returns_its_share_once(self):
        order = self._order()  # $20 of goods paid with $10 credit + $10 cash
        refund = Refund.objects.create(
            order=order, amount=Money(Decimal('5.00'), 'USD'), reason='customer_request'
        )
        for _ in range(2):
            hook_registry.fire(MorpheusEvents.PAYMENT_REFUNDED, refund=refund, order=order)
        self.assertEqual(self._balance(), Decimal('5.00'))  # half the goods, half the credit

    def test_a_guest_cart_is_untouched(self):
        guest = CartService.get_or_create_cart(session_key='guest-credit')
        CartService.add_item(cart=guest, product_id=str(self.product.id))
        breakdown = OrderService.calculate_cart_breakdown(cart=guest, address=ADDRESS)
        self.assertEqual(breakdown['total'].amount, Decimal('20.00'))
