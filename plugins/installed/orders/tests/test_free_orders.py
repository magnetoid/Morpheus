"""A free download goes through the cart, and an order with nothing to pay is paid at once.

dotbooks gives its PDFs away (owner, 2026-11-07). The add-to-cart guard refused
anything priced 0 (18 unpriced products had been buyable for nothing), and
checkout always asked a gateway for a payment intent, which Stripe refuses for
0: a free order, like a cart a gift card covers in full, could not be placed.
Now a free download (`ProductVariant.is_free`) costs 0 in the cart, and an order
whose total is 0 is confirmed and marked paid by checkout itself; ORDER_PAID
then mints the download link like any paid order.
"""

from __future__ import annotations

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.mutations import CompleteOrderInput, OrdersMutationExtension
from plugins.installed.orders.models import Order
from plugins.installed.orders.services import CartService

_ROUTING = 'plugins.installed.payments.services.routing.create_payment_intent_for'


class FreeDownloadCartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Product.objects.create(
            name='Free Cart Book',
            slug='free-cart-book',
            sku='FCB',
            price=Money(Decimal('8.50'), 'USD'),
            product_type='variable',
            status='active',
            localized_prices={'EUR': '8.00'},
        )
        cls.pdf = ProductVariant.objects.create(
            product=cls.book,
            name='Digital PDF',
            sku='FCB-PDF',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
        )
        cls.zero_print = ProductVariant.objects.create(
            product=cls.book, name='Print', sku='FCB-P', price=Money(0, 'USD')
        )
        cls.unpriced = Product.objects.create(
            name='Unpriced', slug='unpriced', sku='UNP', price=Money(0, 'USD'), status='active'
        )

    def _cart(self, key):
        return CartService.get_or_create_cart(session_key=key)

    def test_a_free_download_goes_in_the_cart_at_0(self):
        cart = self._cart('free-1')
        item = CartService.add_item(cart, str(self.book.id), variant_id=str(self.pdf.id))
        self.assertEqual(item.unit_price, Money(0, 'USD'))

    def test_a_printed_edition_priced_0_costs_the_book_price(self):
        cart = self._cart('free-2')
        item = CartService.add_item(cart, str(self.book.id), variant_id=str(self.zero_print.id))
        self.assertEqual(item.unit_price, Money(Decimal('8.50'), 'USD'))

    def test_an_unpriced_product_is_still_not_for_sale(self):
        with self.assertRaisesMessage(ValueError, 'not available to buy yet'):
            CartService.add_item(self._cart('free-3'), str(self.unpriced.id))

    def test_the_book_price_in_another_currency_does_not_price_the_free_download(self):
        cart = self._cart('free-4')
        item = CartService.add_item(
            cart, str(self.book.id), variant_id=str(self.pdf.id), currency='EUR'
        )
        self.assertEqual(item.unit_price, Money(0, 'EUR'))


class FreeOrderCheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.book = Product.objects.create(
            name='Free Order Book',
            slug='free-order-book',
            sku='FOB',
            price=Money(Decimal('8.50'), 'USD'),
            product_type='variable',
            status='active',
        )
        cls.pdf = ProductVariant.objects.create(
            product=cls.book,
            name='Digital PDF',
            sku='FOB-PDF',
            price=Money(0, 'USD'),
            variant_type='digital',
            requires_shipping=False,
            # A stored name is all the download app checks; no file is written.
            digital_file='digital/variants/free-order-book.pdf',
        )
        cls.printed = ProductVariant.objects.create(
            product=cls.book, name='Print', sku='FOB-P', variant_type='physical'
        )

    def setUp(self):
        self.session = SessionStore()
        self.session.create()
        self.cart = CartService.get_or_create_cart(session_key=self.session.session_key)

    def _complete(self):
        request = RequestFactory().post('/graphql/')
        request.session = self.session
        request.user = AnonymousUser()
        info = mock.Mock()
        info.context = {'request': request}
        inp = CompleteOrderInput(
            cart_id=str(self.cart.pk),
            email='reader@x.test',
            shipping_address=AddressInput(country='US'),
        )
        return OrdersMutationExtension().complete_order(info, inp)

    def test_a_free_order_is_paid_without_a_gateway(self):
        CartService.add_item(self.cart, str(self.book.id), variant_id=str(self.pdf.id))
        with (
            mock.patch(_ROUTING) as routing,
            self.captureOnCommitCallbacks(execute=True),
        ):
            payload = self._complete()
        self.assertEqual(payload.errors, [])
        routing.assert_not_called()
        self.assertEqual(payload.payment_client_secret, '')
        order = Order.objects.get(order_number=payload.order_number)
        self.assertEqual(order.total.amount, 0)
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.status, 'confirmed')

    def test_the_free_order_gets_its_download_link(self):
        from plugins.installed.digital_products.models import DownloadToken

        CartService.add_item(self.cart, str(self.book.id), variant_id=str(self.pdf.id))
        with mock.patch(_ROUTING), self.captureOnCommitCallbacks(execute=True):
            payload = self._complete()
        order = Order.objects.get(order_number=payload.order_number)
        self.assertEqual(DownloadToken.objects.filter(order=order).count(), 1)

    def test_an_order_with_something_to_pay_still_goes_to_the_gateway(self):
        CartService.add_item(self.cart, str(self.book.id), variant_id=str(self.printed.id))
        with mock.patch(_ROUTING, return_value={'success': True, 'client_secret': 'cs'}) as r:
            payload = self._complete()
        r.assert_called_once()
        self.assertEqual(payload.payment_client_secret, 'cs')
        order = Order.objects.get(order_number=payload.order_number)
        self.assertNotEqual(order.payment_status, 'paid')
