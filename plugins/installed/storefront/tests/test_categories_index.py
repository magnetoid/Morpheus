"""`/categories/` is the shell's own page again, not a book-vertical redirect.

`book_product` migrated categories→genres and replaced this view with an
UNCONDITIONAL `redirect('/genres/', permanent=True)` — a vertical's decision
hardcoded in the shared shell. Consequences on every non-book store: the index
died (both themes still ship `categories.html`), `/categories/` 301'd to a path
only an optional plugin mounts, and `seo/services/sitemaps.py` went on listing
`/categories/` — so the sitemap invited crawlers to a permanent redirect. The
Sep 2026 audit caught it live as "a canonical pointing outside the sitemap".
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.registry import app_registry


class CategoriesIndexTests(TestCase):
    def test_redirects_to_genres_while_the_book_vertical_is_active(self):
        if not app_registry.is_active('book_product'):
            self.skipTest('book_product inactive in this configuration')
        r = self.client.get('/categories/')
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r['Location'], '/genres/')

    def test_renders_the_shell_index_when_the_book_vertical_is_off(self):
        was_active = app_registry.is_active('book_product')
        if was_active:
            app_registry.deactivate('book_product')
            cache.clear()
            self.addCleanup(cache.clear)
            self.addCleanup(app_registry.activate, 'book_product')

        r = self.client.get('/categories/')
        self.assertEqual(r.status_code, 200, 'the categories index must not 301 into a 404')
        self.assertTemplateUsed(r, 'storefront/categories.html')

    def _sitemap_paths(self) -> set[str]:
        # The MERGED list: `/categories/` is the storefront's to contribute, and
        # reading only seo's native generator made these assertions vacuous.
        from plugins.installed.seo.services.sitemaps import _merged_sitemap_entries

        return {
            '/' + e['loc'].split('/', 3)[3] if e['loc'].count('/') > 2 else '/'
            for e in _merged_sitemap_entries()
        }

    def _book_vertical_off(self) -> None:
        if app_registry.is_active('book_product'):
            app_registry.deactivate('book_product')
            cache.clear()
            self.addCleanup(cache.clear)
            self.addCleanup(app_registry.activate, 'book_product')

    def test_the_book_vertical_keeps_the_redirect_out_of_the_sitemap(self):
        if not app_registry.is_active('book_product'):
            self.skipTest('book_product inactive in this configuration')
        self.assertNotIn(
            '/categories/',
            self._sitemap_paths(),
            'the book vertical 301s /categories/, so it must not be in the sitemap',
        )

    def test_the_index_is_listed_only_once_a_category_has_products(self):
        # Both directions, because a vacuous pass is how this shipped: seo
        # listed the route unconditionally and nothing ever fetched it — and on
        # the travel store the index it advertised linked seven empty categories.
        from decimal import Decimal

        from djmoney.money import Money

        from plugins.installed.catalog.models import Category, Product

        self._book_vertical_off()
        Category.objects.update(is_active=False)  # whatever a seed left behind
        shelf = Category.objects.create(name='Index shelf', slug='index-shelf')
        self.assertNotIn('/categories/', self._sitemap_paths())

        Product.objects.create(
            name='Shelved',
            slug='shelved',
            sku='SHELVED-1',
            price=Money(Decimal('5.00'), 'USD'),
            product_type='simple',
            status='active',
            category=shelf,
        )
        self.assertIn('/categories/', self._sitemap_paths())
        self.assertEqual(self.client.get('/categories/').status_code, 200)

    def test_sitemap_drops_the_entry_when_the_book_vertical_is_toggled_on(self):
        was_active = app_registry.is_active('book_product')
        if not was_active:
            app_registry.activate('book_product')
            cache.clear()
            self.addCleanup(cache.clear)
            self.addCleanup(app_registry.deactivate, 'book_product')
        self.assertNotIn('/categories/', self._sitemap_paths())
