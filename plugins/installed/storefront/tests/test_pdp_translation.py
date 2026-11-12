"""The product page shows a reviewed translation on /sr/ (v0.160.0)."""

from __future__ import annotations

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from core.i18n.services import set_translation

BILINGUAL = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}


@override_settings(**BILINGUAL)
class ProductPageTranslationTests(TestCase):
    def setUp(self):
        cache.clear()
        from plugins.installed.catalog.models import Product

        self.product = Product.objects.create(
            name='Night Sky Atlas',
            slug='night-sky-atlas',
            sku='NSA-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
            short_description='<p>Every constellation, mapped.</p>',
            description='<p>A field guide to the stars.</p>',
        )

    def _body(self, path):
        cache.clear()
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _translate(self):
        set_translation(self.product, 'name', 'sr', 'Atlas noćnog neba')
        set_translation(self.product, 'short_description', 'sr', '<p>Sva sazvežđa.</p>')
        set_translation(self.product, 'description', 'sr', '<p>Vodič kroz zvezde.</p>')

    def test_the_serbian_page_shows_the_reviewed_translation(self):
        self._translate()
        body = self._body('/sr/products/night-sky-atlas/')
        self.assertIn('Atlas noćnog neba', body)
        self.assertIn('Vodič kroz zvezde.', body)
        self.assertNotIn('A field guide to the stars.', body)

    def test_the_english_page_is_unchanged(self):
        self._translate()
        body = self._body('/products/night-sky-atlas/')
        self.assertIn('Night Sky Atlas', body)
        self.assertNotIn('Atlas noćnog neba', body)

    def test_a_draft_is_not_shown(self):
        set_translation(self.product, 'name', 'sr', 'Atlas noćnog neba', reviewed=False)
        set_translation(self.product, 'short_description', 'sr', '<p>Sva.</p>', reviewed=False)
        set_translation(self.product, 'description', 'sr', '<p>Vodič.</p>', reviewed=False)
        self.assertNotIn('Atlas noćnog neba', self._body('/sr/products/night-sky-atlas/'))

    def test_the_view_leaves_the_row_in_english(self):
        self._translate()
        self._body('/sr/products/night-sky-atlas/')
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, 'Night Sky Atlas')
