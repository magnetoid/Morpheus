"""Under every theme, a product sold in one form shows no variant picker
(v0.152.0): the default variant that counts its stock is not a choice. A product
with real choices still shows one, and both still post a variant to the cart."""

from __future__ import annotations

from decimal import Decimal

from django.apps import apps
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.catalog.models import Product, ProductVariant
from plugins.installed.catalog.variants import ensure_stock_variant
from themes.registry import theme_registry

THEMES = ['dot_books', 'supernatural_shop', 'irving_survival']
if apps.is_installed('plugins.installed.booking_marketplace'):
    THEMES += ['montenegro', 'croatia']

PICKER = 'id="pdp-variants-label"'


class DefaultVariantPickerTests(TestCase):
    def setUp(self):
        self.one_form = Product.objects.create(
            name='Plain mug', slug='plain-mug', sku='PLAIN', status='active', price=8
        )
        self.default = ensure_stock_variant(self.one_form)
        self.sized = Product.objects.create(
            name='Sized tee', slug='sized-tee', sku='SIZED', status='active', price=20
        )
        for size in ('S', 'M'):
            ProductVariant.objects.create(
                product=self.sized,
                name=size,
                sku=f'SIZED-{size}',
                size=size,
                price=Money(Decimal('20'), 'USD'),
            )

    def use_theme(self, name):
        override = override_settings(MORPHEUS_ACTIVE_THEME=name)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        self.addCleanup(setattr, theme_registry, '_active_name', previous)
        theme_registry.set_active(name)

    def test_the_picker_shows_only_for_real_choices(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                self.use_theme(theme)
                plain = self.client.get('/products/plain-mug/')
                self.assertEqual(plain.status_code, 200)
                html = plain.content.decode()
                self.assertNotIn(PICKER, html)
                self.assertIn(str(self.default.pk), html)  # still sent to the cart
                sized = self.client.get('/products/sized-tee/').content.decode()
                self.assertIn(PICKER, sized)
