"""Under every theme, "Withdraw from contract here" is on the customer's order
page and in the footer while returns_portal's withdrawal function is on, and on
neither while it is off (EU CRD Art. 11a; v0.181.0). The order page emits the
``account_order_actions`` slot; the footer link comes through ``footer_legal``."""

from __future__ import annotations

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.orders.models import Order
from plugins.testing import set_app_settings
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

LABEL = 'Withdraw from contract here'


class WithdrawalLinkTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='buyer', email='buyer@example.com', password='pw-12345'
        )
        self.order = Order.objects.create(
            customer=self.buyer,
            email='buyer@example.com',
            subtotal=Money(20, 'USD'),
            total=Money(20, 'USD'),
        )
        self.client.force_login(self.buyer)

    def use_theme(self, name):
        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def test_the_order_page_and_the_footer_link_the_function_while_it_is_on(self):
        order_link = f'href="/withdraw/?order={self.order.order_number}"'
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                set_app_settings(self, 'returns_portal', withdrawal_function=False)
                page = self.client.get(f'/account/orders/{self.order.order_number}/')
                self.assertEqual(page.status_code, 200)
                self.assertNotIn(LABEL, page.content.decode())
                set_app_settings(self, 'returns_portal', withdrawal_function=True)
                html = self.client.get(
                    f'/account/orders/{self.order.order_number}/'
                ).content.decode()
                self.assertIn(order_link, html)
                self.assertIn('href="/withdraw/"', html)
