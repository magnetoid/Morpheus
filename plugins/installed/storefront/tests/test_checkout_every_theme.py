"""Checkout renders under every shipped theme.

Each theme ships its own checkout template, and an error there is a 500 on the
one page that takes money — while the rest of the storefront suite renders the
default theme only. (The montenegro theme needs the booking app, which only
some runs install.)
"""

from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES.append('montenegro')


class CheckoutEveryThemeTests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            name='Theme Book', slug='theme-book', sku='T-1',
            price=Money(Decimal('12.00'), 'USD'), status='active',
        )  # fmt: skip
        self.client.post(f'/cart/add/{product.id}/', {'quantity': 1})

    def test_the_checkout_renders_in_every_theme(self):
        for name in THEMES:
            with self.subTest(theme=name):
                override = override_settings(MORPHEUS_ACTIVE_THEME=name)
                override.enable()
                previous = theme_registry._active_name
                theme_registry.set_active(name)
                try:
                    response = self.client.get('/checkout/quick/', follow=True)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'name="email"')
                finally:
                    theme_registry._active_name = previous
                    override.disable()
