"""Montenegro's shell has no dead ends.

The header linked a cart the booking marketplace never fills, and the
sign-in-code pages dropped from the branded site into the generic account
shell.
"""

from __future__ import annotations

from django.test import TestCase

from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin

# The theme's card, as on its own login page — the generic shell has no such class.
THEME_CARD = 'rounded-2xl border border-border shadow-card bg-card'


class MontenegroShellTests(MontenegroThemeMixin, TestCase):
    def test_the_sign_in_code_page_is_branded(self):
        body = self.client.get('/auth/otp/', follow=True).content.decode()
        self.assertIn(THEME_CARD, body)
        self.assertIn('name="email"', body)

    def test_an_empty_cart_is_not_linked(self):
        body = self.client.get('/', follow=True).content.decode()
        self.assertNotIn('href="/cart/"', body)
