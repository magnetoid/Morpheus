"""A download can't be paid in cash on delivery (owner, 2026-11-11).

The courier collects the money when the parcel arrives, and a download never
arrives by courier: checkout leaves cash on delivery out of the picker for a
cart with a line that does not ship, and the server refuses it for such an
order whatever the browser posted.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Cart, CartItem, Order, OrderItem
from plugins.installed.payments.gateway import gateway_registry
from plugins.installed.payments.models import PaymentGatewayConfig
from plugins.installed.payments.services import routing

NO_STRIPE = override_settings(STRIPE_SECRET_KEY='', STRIPE_PUBLIC_KEY='')
BANK_DETAILS = {'instructions': 'Wire to IBAN 123.'}


def _product(slug, *, ships):
    return Product.objects.create(
        name=slug.title(),
        slug=slug,
        sku=slug.upper(),
        status='active',
        product_type='simple' if ships else 'digital',
        requires_shipping=ships,
        price=Money(Decimal('8.00'), 'USD'),
    )


def _order(*products):
    order = Order.objects.create(
        email='shopper@example.com',
        subtotal=Money(Decimal('8'), 'USD'),
        total=Money(Decimal('8'), 'USD'),
    )
    for product in products:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            sku=product.sku,
            quantity=1,
            unit_price=Money(8, 'USD'),
            total_price=Money(8, 'USD'),
        )
    return order


def _gateway_of(order):
    return Order.objects.values_list('payment_gateway', flat=True).get(pk=order.pk)


@NO_STRIPE
class CashOnDeliveryForDownloadsTests(TestCase):
    def setUp(self):
        PaymentGatewayConfig.objects.update_or_create(slug='cod', defaults={'enabled': True})
        PaymentGatewayConfig.objects.update_or_create(
            slug='manual', defaults={'enabled': True, 'config': BANK_DETAILS}
        )
        self.book = _product('paperback', ships=True)
        self.pdf = _product('ebook', ships=False)

    def test_the_picker_leaves_it_out_for_a_cart_with_a_download(self):
        self.assertIn('cod', [m['slug'] for m in routing.picker_gateways()])
        self.assertNotIn('cod', [m['slug'] for m in routing.picker_gateways(ships=False)])

    def test_it_is_never_the_default_for_a_download(self):
        PaymentGatewayConfig.objects.filter(slug='manual').update(enabled=False)
        self.assertEqual(gateway_registry.default().slug, 'cod')
        self.assertIsNone(gateway_registry.default(ships=False))

    def test_an_order_of_parcels_can_still_pay_on_delivery(self):
        order = _order(self.book)
        self.assertTrue(routing.create_payment_intent_for(order, 'cod')['success'])
        self.assertEqual(_gateway_of(order), 'cod')

    def test_a_posted_cod_choice_for_a_download_goes_to_another_method(self):
        order = _order(self.pdf)
        result = routing.create_payment_intent_for(order, 'cod')
        self.assertTrue(result['success'])
        self.assertEqual(_gateway_of(order), 'manual')

    def test_a_mixed_order_is_not_paid_on_delivery_either(self):
        order = _order(self.book, self.pdf)
        routing.create_payment_intent_for(order, 'cod')
        self.assertEqual(_gateway_of(order), 'manual')

    def test_a_store_with_only_cash_on_delivery_says_why(self):
        PaymentGatewayConfig.objects.filter(slug='manual').update(enabled=False)
        order = _order(self.pdf)
        result = routing.create_payment_intent_for(order, 'cod')
        self.assertFalse(result['success'])
        self.assertIn("Downloads can't be paid in cash on delivery", result['error'])
        self.assertNotEqual(_gateway_of(order), 'cod')

    def test_the_checkout_picker_asks_with_the_cart_s_lines(self):
        from plugins.installed.storefront.views.checkout_one_page import _payment_methods

        cart = Cart.objects.create(session_key='cod-downloads')
        request = RequestFactory().get('/checkout/')
        request.session = SessionStore()
        request.session['cart_id'] = str(cart.pk)
        request.user = None
        CartItem.objects.create(
            cart=cart, product=self.book, quantity=1, unit_price=Money(8, 'USD')
        )
        self.assertIn('cod', [m['slug'] for m in _payment_methods(request)])
        CartItem.objects.create(cart=cart, product=self.pdf, quantity=1, unit_price=Money(8, 'USD'))
        self.assertNotIn('cod', [m['slug'] for m in _payment_methods(request)])
