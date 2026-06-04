"""Book taxonomies dashboard — per-term SEO editing + facet page wiring."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.book_product.models import BookProduct, BookTaxonomyTerm
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


class BookTaxonomiesDashboardTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='tx', email='t@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        _book('a', 'A-1', author='Jane Doe', publisher='Acme Press')

    def test_list_shows_terms(self):
        r = self.client.get(reverse('book_product_dashboard:taxonomies'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Jane Doe')
        self.assertContains(r, 'Acme Press')

    def test_edit_creates_term_with_seo(self):
        url = reverse('book_product_dashboard:taxonomy_edit', args=['author', 'jane-doe'])
        r = self.client.post(
            url,
            {
                'name': 'Jane Doe',
                'description': 'Booker-winning novelist.',
                'meta_title': 'Jane Doe — books',
                'meta_description': 'All books by Jane Doe.',
            },
        )
        self.assertEqual(r.status_code, 302)
        term = BookTaxonomyTerm.objects.get(taxonomy='author', slug='jane-doe')
        self.assertEqual(term.meta_title, 'Jane Doe — books')
        self.assertEqual(term.description, 'Booker-winning novelist.')

    def test_facet_page_uses_term_seo(self):
        BookTaxonomyTerm.objects.create(
            taxonomy='publisher',
            slug='acme-press',
            name='Acme Press',
            meta_title='Acme Press — our list',
            description='Indie powerhouse.',
        )
        r = self.client.get('/publisher/acme-press/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Acme Press — our list')  # SEO title
        self.assertContains(r, 'Indie powerhouse.')  # intro blurb
