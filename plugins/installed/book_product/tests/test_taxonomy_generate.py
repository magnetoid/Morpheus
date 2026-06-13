"""Taxonomy AI text assist — generate + rewrite endpoint."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct
from plugins.installed.catalog.models import Product


def _book(slug, sku, **kw):
    p = Product.objects.create(
        name=slug,
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=p, **kw)


class TaxonomyGenerateTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='g', email='g@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        _book('a', 'A-1', author='Jane Doe')

    def _url(self):
        return reverse('book_product_dashboard:taxonomy_generate', args=['author', 'jane-doe'])

    def test_generate_fills_all_fields(self):
        with patch('plugins.installed.ai_assistant.services.llm.get_llm') as g:
            g.return_value.complete.return_value = (
                '{"description": "Booker novelist.", "meta_title": "Jane Doe books", '
                '"meta_description": "All by Jane Doe."}'
            )
            r = self.client.post(self._url())
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['description'], 'Booker novelist.')
        self.assertEqual(data['meta_title'], 'Jane Doe books')
        self.assertEqual(data['meta_description'], 'All by Jane Doe.')

    def test_rewrite_mode_returns_description(self):
        with patch('plugins.installed.ai_assistant.services.llm.get_llm') as g:
            g.return_value.complete.return_value = '{"description": "Sharper intro."}'
            r = self.client.post(self._url(), {'mode': 'rewrite', 'existing': 'old intro'})
        self.assertEqual(r.json()['description'], 'Sharper intro.')

    def test_root_generate(self):
        with patch('plugins.installed.ai_assistant.services.llm.get_llm') as g:
            g.return_value.complete.return_value = '{"description": "Every author."}'
            r = self.client.post(
                reverse('book_product_dashboard:taxonomy_root_generate', args=['author'])
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['description'], 'Every author.')

    def test_provider_error_is_soft(self):
        with patch(
            'plugins.installed.ai_assistant.services.llm.get_llm',
            side_effect=RuntimeError('no key'),
        ):
            r = self.client.post(self._url())
        self.assertEqual(r.status_code, 200)
        self.assertIn('error', r.json())

    def test_get_rejected(self):
        self.assertEqual(self.client.get(self._url()).status_code, 405)

    def test_unknown_taxonomy_400(self):
        r = self.client.post(
            reverse('book_product_dashboard:taxonomy_generate', args=['nope', 'x'])
        )
        self.assertEqual(r.status_code, 400)
