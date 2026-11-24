"""Every theme shows the delivery estimate (F5).

Under each shipping choice in both checkout forms, on the order's own pages
(the thank-you page and the account's order page) and in the placed email. The
range is shipping's; the order keeps the one the shopper chose.
"""

from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.models import StoreSettings
from plugins.installed.catalog.models import Product
from plugins.installed.orders.models import Order
from plugins.installed.shipping.models import ShippingRate, ShippingZone
from plugins.testing import set_app_settings
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival', 'dawnchild']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

MARKER = 'data-delivery-estimate'
ADDRESS = {
    'email': 'ada@example.com',
    'first_name': 'Ada',
    'last_name': 'L',
    'address_line1': '1 Main',
    'city': 'Podgorica',
    'state': '',
    'postal_code': '81000',
    'country': 'ME',
}


def _use_theme(case, name):
    override = override_settings(MORPHEUS_ACTIVE_THEME=name)
    override.enable()
    case.addCleanup(override.disable)
    previous = theme_registry._active_name
    case.addCleanup(setattr, theme_registry, '_active_name', previous)
    theme_registry.set_active(name)


class CheckoutChoicesTests(TestCase):
    def setUp(self):
        StoreSettings.objects.create(country='ME')
        product = Product.objects.create(
            name='Parcel Book',
            slug='parcel-book',
            sku='PB-1',
            price=Money(Decimal('12.00'), 'EUR'),
            status='active',
            requires_shipping=True,
        )
        zone = ShippingZone.objects.create(name='ME', countries=['ME'])
        ShippingRate.objects.create(
            zone=zone,
            name='Courier',
            computation='flat',
            flat_amount=Money(6, 'EUR'),
            estimated_days_min=2,
            estimated_days_max=4,
        )
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})
        session = self.client.session
        session['checkout_address'] = ADDRESS
        session.save()

    def _pages(self):
        return {
            'three-step': self.client.get('/checkout/shipping/'),
            # The one-page form lists rates once it has an address: here it comes
            # back with the missing email and the rates for the typed address.
            'one-page': self.client.post(
                '/checkout/quick/', {k: v for k, v in ADDRESS.items() if k != 'email'}
            ),
        }

    def test_both_checkout_forms_show_the_range_under_every_theme(self):
        set_app_settings(self, 'shipping', show_delivery_estimate=True)
        for theme in THEMES:
            _use_theme(self, theme)
            for form, response in self._pages().items():
                with self.subTest(theme=theme, form=form):
                    self.assertEqual(response.status_code, 200)
                    html = response.content.decode()
                    self.assertIn('Courier', html)
                    self.assertIn(MARKER, html)
                    self.assertIn('2–4 business days', html)

    def test_nothing_while_off(self):
        for theme in THEMES:
            _use_theme(self, theme)
            for form, response in self._pages().items():
                with self.subTest(theme=theme, form=form):
                    html = response.content.decode()
                    self.assertIn('Courier', html)
                    self.assertNotIn(MARKER, html)


class OrderPagesTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='buyer', email='buyer@example.com', password='pw-12345'
        )
        self.client.force_login(self.buyer)

    def _order(self, metadata):
        return Order.objects.create(
            customer=self.buyer,
            email='buyer@example.com',
            subtotal=Money(20, 'EUR'),
            total=Money(20, 'EUR'),
            metadata=metadata,
        )

    def test_order_pages_show_the_stamp(self):
        stamped = self._order({'delivery_estimate': {'min': 3, 'max': 6}})
        plain = self._order({})
        for theme in THEMES:
            _use_theme(self, theme)
            for order, shown in ((stamped, True), (plain, False)):
                for url in (
                    f'/order/confirmation/{order.order_number}/',
                    f'/account/orders/{order.order_number}/',
                ):
                    with self.subTest(theme=theme, url=url):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200)
                        html = response.content.decode()
                        if shown:
                            self.assertIn(MARKER, html)
                            self.assertIn('3–6 business days', html)
                        else:
                            self.assertNotIn(MARKER, html)

    def test_placed_email_html_and_text(self):
        stamped = self._order({'delivery_estimate': {'min': 3, 'max': 6}})
        plain = self._order({})
        for name in ('emails/order_placed.html', 'emails/order_placed.txt'):
            with self.subTest(template=name):
                self.assertIn('3–6 business days', render_to_string(name, {'order': stamped}))
                self.assertNotIn('Estimated delivery', render_to_string(name, {'order': plain}))
