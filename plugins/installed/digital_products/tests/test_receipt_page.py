"""The thank-you page says where a download is and links no file (owner, 2026-11-14).

A buyer takes a digital purchase from the emailed link or the account's Library,
never from the thank-you page. That page showed a Download button (and an
audiobook's player) beside the line under every theme, with the same file the
order page and the email link to.
"""

from __future__ import annotations

from django.apps import apps
from django.test import override_settings

from plugins.installed.digital_products.tests.test_library import LibraryTestCase

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']


class ReceiptPageTests(LibraryTestCase):
    def use_theme(self, name):
        from themes.registry import theme_registry

        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def _receipt(self, order) -> str:
        url = f'/order/confirmation/{order.order_number}/?token={order.public_token}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _assert_no_file(self, body, line):
        self.assertNotIn('/digital/download/', body)
        self.assertNotIn(f'/account/library/{line.pk}/file/', body)
        self.assertNotIn('<audio', body)

    def test_a_guest_is_pointed_to_the_email(self):
        from plugins.installed.digital_products.app import DigitalProductsPlugin

        order, line = self._order(customer=None, payment_status='paid', status='processing')
        DigitalProductsPlugin().on_order_paid(order)
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                body = self._receipt(order)
                self._assert_no_file(body, line)
                self.assertIn('Download link sent to your email', body)

    def test_a_signed_in_buyer_is_pointed_to_the_library(self):
        order, line = self._order(payment_status='paid', status='processing')
        self.client.force_login(self.buyer)
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                body = self._receipt(order)
                self._assert_no_file(body, line)
                self.assertIn('In your Library and your email', body)

    def test_a_payment_still_on_its_way_says_when_the_link_comes(self):
        order, line = self._order(customer=None, payment_status='unpaid', status='pending')
        self.use_theme('dot_books')
        body = self._receipt(order)
        self._assert_no_file(body, line)
        self.assertIn('Download link emailed once the payment goes through', body)

    def test_the_account_order_page_keeps_its_download(self):
        order, line = self._order(payment_status='paid', status='processing')
        self.client.force_login(self.buyer)
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                body = self.client.get(f'/account/orders/{order.order_number}/').content.decode()
                self.assertIn(f'/account/library/{line.pk}/file/', body)
