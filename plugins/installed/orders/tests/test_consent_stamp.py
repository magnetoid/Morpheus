"""The order carries the shopper's consent from checkout.

ORDER_PAID fires from a payment webhook, a staff click or an agent — never from
the shopper's browser — so the conversion APIs need the choice on the order.
"""

from __future__ import annotations

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.graphql.inputs import AddressInput
from plugins.installed.orders.graphql.mutations import CompleteOrderInput, OrdersMutationExtension
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.installed.orders.services import CartService, OrderService


def _set_gdpr(on: bool) -> None:
    from core.models import StoreSettings

    row = StoreSettings.objects.first() or StoreSettings()
    row.gdpr_enabled = on
    row.save()
    cache.delete('morph:gdpr_enabled')


class CreateFromCartStampTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name='Stamp Book',
            slug='stamp-book',
            sku='STAMP',
            price=Money(10, 'USD'),
            status='active',
        )
        self.addr = {'first_name': 'S', 'last_name': 'T', 'line1': '1 Main', 'country': 'US'}

    def _cart(self, key):
        cart = CartService.get_or_create_cart(session_key=key)
        CartService.add_item(cart, str(self.product.id), quantity=1)
        return cart

    def test_the_consent_given_is_stored_on_the_order(self):
        consent = {'managed': True, 'analytics': True, 'marketing': False}
        order = OrderService.create_from_cart(
            self._cart('c1'), 'a@x.test', self.addr, self.addr, consent=consent
        )
        self.assertEqual(order.metadata['consent'], consent)

    def test_no_consent_argument_stores_no_stamp(self):
        order = OrderService.create_from_cart(self._cart('c2'), 'b@x.test', self.addr, self.addr)
        self.assertNotIn('consent', order.metadata)


class CompleteOrderPassesTheStampTests(TestCase):
    """The storefront checkout stamps the visitor's cookie decision."""

    def setUp(self):
        _set_gdpr(True)
        self.session = SessionStore()
        self.session.create()
        product = Product.objects.create(
            name='Routed',
            slug='stamp-routed',
            sku='STAMP-R',
            price=Money(Decimal('5'), 'USD'),
            status='active',
        )
        self.cart = Cart.objects.create(session_key=self.session.session_key)
        CartItem.objects.create(
            cart=self.cart, product=product, quantity=1, unit_price=Money(Decimal('5'), 'USD')
        )

    def _info(self, cookie=None):
        request = RequestFactory().post('/graphql/')
        request.session = self.session
        request.user = AnonymousUser()
        if cookie is not None:
            request.COOKIES['morpheus_consent'] = json.dumps(cookie)
        info = mock.Mock()
        info.context = {'request': request}
        return info

    def _complete(self, info):
        order = Order.objects.create(
            email='s@x.test', subtotal=Money(Decimal('5'), 'USD'), total=Money(Decimal('5'), 'USD')
        )
        inp = CompleteOrderInput(
            cart_id=str(self.cart.pk),
            email='s@x.test',
            shipping_address=AddressInput(country='US'),
            payment_gateway='manual',
        )
        with (
            mock.patch(
                'plugins.installed.orders.services.OrderService.create_from_cart',
                return_value=order,
            ) as create,
            mock.patch(
                'plugins.installed.payments.services.routing.create_payment_intent_for',
                return_value={'success': True, 'client_secret': ''},
            ),
        ):
            OrdersMutationExtension().complete_order(info, inp)
        return create.call_args.kwargs['consent']

    def test_a_shopper_who_accepted_marketing_is_stamped_yes(self):
        consent = self._complete(self._info({'necessary': True, 'marketing': True}))
        self.assertEqual(consent, {'managed': True, 'analytics': False, 'marketing': True})

    def test_a_shopper_who_never_answered_is_stamped_no(self):
        consent = self._complete(self._info())
        self.assertEqual(consent, {'managed': True, 'analytics': False, 'marketing': False})
