"""Taxonomy root listing pages (/authors/ …) + their dashboard landing editor."""

# ruff: noqa: PLC0415
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.book_product.models import BookTaxonomyRoot
from plugins.installed.catalog.models import Product


def _book(slug, sku, **kw):
    from plugins.installed.book_product.models import BookProduct

    p = Product.objects.create(
        name=slug,
        slug=slug,
        sku=sku,
        price=Money(Decimal('9.00'), 'USD'),
        product_type='simple',
        status='active',
    )
    return BookProduct.objects.create(product=p, **kw)


class TaxonomyRootStorefrontTests(TestCase):
    def test_authors_index_lists_authors_and_links_detail(self):
        _book('a', 'A-1', author='Jane Doe')
        _book('b', 'B-1', author='John Roe')
        r = self.client.get('/authors/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Jane Doe')
        self.assertContains(r, 'John Roe')
        self.assertContains(r, '/author/jane-doe/')  # links to the detail page

    def test_publishers_series_imprints_indexes_render(self):
        _book('p', 'P-1', publisher='Acme Press', series='Saga', imprint='Vintage')
        for url, value in [
            ('/publishers/', 'Acme Press'),
            ('/series/', 'Saga'),
            ('/imprints/', 'Vintage'),
        ]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, value)

    def test_empty_index_still_200(self):
        r = self.client.get('/authors/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'full catalogue')  # the empty-state copy

    def test_root_seo_and_intro_render(self):
        _book('a', 'A-1', author='Jane Doe')
        BookTaxonomyRoot.objects.create(
            taxonomy='author',
            description='Every author we stock.',
            meta_title='All authors — dot books',
        )
        r = self.client.get('/authors/')
        self.assertContains(r, 'All authors — dot books')  # SEO title in <title>
        self.assertContains(r, 'Every author we stock.')  # intro blurb

    def test_detail_breadcrumb_links_up_to_index(self):
        _book('p', 'P-1', publisher='Acme Press')
        r = self.client.get('/publisher/acme-press/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'href="/publishers/"')  # "Publisher" links to its index


class TaxonomyRootDashboardTests(TestCase):
    def setUp(self):
        u = get_user_model().objects.create_user(
            username='tx', email='t@example.test', password='pw', is_staff=True
        )
        self.client.force_login(u)
        _book('a', 'A-1', author='Jane Doe')

    def test_landing_editor_creates_root_with_seo(self):
        url = reverse('book_product_dashboard:taxonomy_root_edit', args=['author'])
        r = self.client.post(
            url,
            {
                'description': 'All our authors.',
                'meta_title': 'Authors — dot books',
                'meta_description': 'Browse every author.',
            },
        )
        self.assertEqual(r.status_code, 302)
        root = BookTaxonomyRoot.objects.get(taxonomy='author')
        self.assertEqual(root.meta_title, 'Authors — dot books')
        self.assertEqual(root.description, 'All our authors.')

    def test_unknown_taxonomy_redirects(self):
        url = reverse('book_product_dashboard:taxonomy_root_edit', args=['nonsense'])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)

    def test_list_has_landing_edit_links(self):
        r = self.client.get(reverse('book_product_dashboard:taxonomies'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(
            r, reverse('book_product_dashboard:taxonomy_root_edit', args=['author'])
        )
