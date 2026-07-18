"""EU digital-goods withdrawal waiver (Dir 2011/83/EU art. 16(m)).

A cart containing a downloadable/digital item (requires_shipping=False) must
carry the shopper's ticked acknowledgement before checkout can supply the
content; the acknowledgement is recorded on the order. A physical-only cart is
never gated. Exercised at the helper level (both checkout paths share these)
plus the config default.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem, Order
from plugins.installed.storefront.views.checkout import (
    _cart_has_digital,
    _withdrawal_waiver,
    record_waiver,
    waiver_gate,
)

# The waiver ships OFF by default (merchant enables once wording is finalised),
# so the gate tests force it on to exercise the gating logic.
_ENABLED = {
    'enabled': True,
    'text': 'I acknowledge I lose my 14-day right of withdrawal on immediate access.',
}
_WAIVER_FN = 'plugins.installed.storefront.views.checkout._withdrawal_waiver'


def _product(slug, *, requires_shipping):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        status='active',
        price=Money(Decimal('10'), 'USD'),
        requires_shipping=requires_shipping,
    )


def _cart_with(*products):
    cart = Cart.objects.create(session_key='s-waiver')
    for p in products:
        CartItem.objects.create(cart=cart, product=p, quantity=1, unit_price=p.price)
    return cart


def _request(cart_id, **post):
    request = RequestFactory().post('/checkout/quick/', post)
    request.session = {'cart_id': str(cart_id)} if cart_id else {}
    return request


class CartDigitalDetectionTests(TestCase):
    def test_digital_item_detected(self):
        cart = _cart_with(_product('ebook', requires_shipping=False))
        self.assertTrue(_cart_has_digital(_request(cart.id)))

    def test_physical_only_not_digital(self):
        cart = _cart_with(_product('paperback', requires_shipping=True))
        self.assertFalse(_cart_has_digital(_request(cart.id)))

    def test_mixed_cart_is_digital(self):
        cart = _cart_with(
            _product('paperback', requires_shipping=True),
            _product('ebook', requires_shipping=False),
        )
        self.assertTrue(_cart_has_digital(_request(cart.id)))

    def test_no_cart_not_digital(self):
        self.assertFalse(_cart_has_digital(_request(None)))


@patch(_WAIVER_FN, return_value=_ENABLED)
class WaiverGateTests(TestCase):
    def test_digital_cart_unticked_is_blocked(self, _mock):
        cart = _cart_with(_product('ebook', requires_shipping=False))
        self.assertIn('acknowledgement', waiver_gate(_request(cart.id)))

    def test_digital_cart_ticked_passes(self, _mock):
        cart = _cart_with(_product('ebook', requires_shipping=False))
        self.assertEqual(waiver_gate(_request(cart.id, digital_withdrawal_waiver='1')), '')

    def test_physical_cart_never_gated(self, _mock):
        cart = _cart_with(_product('paperback', requires_shipping=True))
        self.assertEqual(waiver_gate(_request(cart.id)), '')

    def test_disabled_waiver_never_gates(self, mock):
        mock.return_value = {'enabled': False, 'text': 'x'}
        cart = _cart_with(_product('ebook', requires_shipping=False))
        self.assertEqual(waiver_gate(_request(cart.id)), '')  # off → digital cart passes


class WaiverConfigAndRecordTests(TestCase):
    def test_default_config_is_off_with_text(self):
        w = _withdrawal_waiver()
        self.assertFalse(w['enabled'])  # ships OFF; merchant enables in Settings
        self.assertIn('withdrawal', w['text'].lower())  # default text still present

    def test_record_stamps_order_metadata(self):
        order = Order.objects.create(
            email='b@example.com',
            subtotal=Money(Decimal('10'), 'USD'),
            total=Money(Decimal('10'), 'USD'),
        )
        record_waiver(order.order_number)
        # django-fsm blocks refresh_from_db() on the protected status field —
        # re-fetch instead (the idiom across the orders tests).
        fresh = Order.objects.get(pk=order.pk)
        waiver = fresh.metadata.get('digital_withdrawal_waiver')
        self.assertIsNotNone(waiver)
        self.assertTrue(waiver['accepted'])
        self.assertIn('withdrawal', waiver['text'].lower())
        self.assertIn('at', waiver)

    def test_record_noop_on_empty_order_no(self):
        record_waiver('')  # must not raise
