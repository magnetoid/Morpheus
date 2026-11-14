"""The dashboard product list's columns: categories, collections, type and date added.

The list showed only the primary category, so a store that files products by
cross-listing (or a book store, whose books carry genres instead) saw a dash in every
row, and nothing said when a product was added or which collections it is in. The
Columns menu hides any column in this browser; it must list every column the table
draws, contributed ones included.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import dateformat, timezone
from djmoney.money import Money

from plugins.installed.catalog.models import Category, Collection, Product
from plugins.testing import hold_app_settings

URL = '/dashboard/products/'


def _product(slug: str, **extra) -> Product:
    return Product.objects.create(
        name=f'Item {slug}',
        slug=slug,
        sku=f'SKU-{slug}',
        status='active',
        price=Money(Decimal('9.00'), 'USD'),
        **extra,
    )


def _row(body: str, slug: str) -> str:
    """The table row of the product whose SKU is ``SKU-<slug>``."""
    rows = re.findall(r'<tr\b.*?</tr>', body, flags=re.S)
    matching = [r for r in rows if f'SKU-{slug}<' in r]
    assert len(matching) == 1, f'expected one row for {slug}, got {len(matching)}'
    return matching[0]


def _cell(row: str, key: str) -> str:
    match = re.search(rf'<td\b[^>]*data-col="{key}"[^>]*>(.*?)</td>', row, flags=re.S)
    assert match, f'no {key} cell'
    return match.group(1).strip()


class ProductListColumnTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='lister', email='lister@example.com', password='x', is_staff=True
        )
        self.client.force_login(user)

    def _body(self, **params) -> str:
        response = self.client.get(URL, params)
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_category_lists_the_primary_first_then_cross_listings_once(self):
        primary = Category.objects.create(name='Qzprimary', slug='qzprimary')
        extra = Category.objects.create(name='Qzextra', slug='qzextra')
        product = _product('cats', category=primary)
        product.additional_categories.add(extra, primary)

        cell = _cell(_row(self._body(), 'cats'), 'category')

        self.assertIn('title="Qzprimary, Qzextra"', cell)
        self.assertIn('>Qzprimary <span class="text-xs">+1</span>', cell)

    def test_a_product_only_cross_listed_shows_its_categories(self):
        product = _product('crossonly')
        product.additional_categories.add(Category.objects.create(name='Qzonly', slug='qzonly'))

        self.assertIn('Qzonly', _cell(_row(self._body(), 'crossonly'), 'category'))

    def test_collections_cell(self):
        product = _product('colls')
        product.collections.add(
            Collection.objects.create(name='Qzsummer', slug='qzsummer', sort_order=1),
            Collection.objects.create(name='Qzwinter', slug='qzwinter', sort_order=2),
        )
        _product('nocoll')
        body = self._body()

        cell = _cell(_row(body, 'colls'), 'collections')
        self.assertIn('title="Qzsummer, Qzwinter"', cell)
        self.assertIn('+1', cell)
        self.assertEqual(_cell(_row(body, 'nocoll'), 'collections'), '—')

    def test_type_and_date_added(self):
        product = _product('typed', product_type='digital')
        row = _row(self._body(), 'typed')

        self.assertEqual(_cell(row, 'type'), product.get_product_type_display())
        self.assertEqual(
            _cell(row, 'added'), dateformat.format(timezone.localtime(product.created_at), 'j M Y')
        )

    def test_added_sorts_by_creation_date(self):
        older, newer = _product('older'), _product('newer')
        Product.objects.filter(pk=older.pk).update(created_at=newer.created_at.replace(year=2020))

        body = self._body(sort='-created_at')
        self.assertIn('sort=created_at', body)
        self.assertLess(body.index('SKU-newer<'), body.index('SKU-older<'))
        body = self._body(sort='created_at')
        self.assertLess(body.index('SKU-older<'), body.index('SKU-newer<'))

    def test_columns_menu_lists_every_hideable_column_the_table_draws(self):
        _product('menu')
        body = self._body()

        header = re.search(r'<thead>.*?</thead>', body, flags=re.S).group(0)
        drawn = re.findall(r'data-col="([^"]+)"', header)
        menu = re.search(r'<details[^>]*data-column-chooser.*?</details>', body, flags=re.S).group(
            0
        )
        offered = re.findall(r'type="checkbox" value="([^"]+)"', menu)

        self.assertEqual(offered, drawn)
        for key in ('sku', 'category', 'collections', 'type', 'vendor', 'added'):
            self.assertIn(key, offered)
        # Every cell of a row carries one of the menu's keys, so hiding works per column.
        self.assertEqual(re.findall(r'data-col="([^"]+)"', _row(body, 'menu')), drawn)

    def test_the_columns_menu_decides_on_a_phone_too(self):
        # base.html hides `.hide-sm` cells under 640px whatever the menu says, so a
        # column the menu controls must not carry it (the script starts a phone with
        # the optional columns off instead, until the merchant ticks one).
        _product('phone')
        body = self._body()

        cells = re.findall(r'<t[hd]\b[^>]*data-col="[^"]+"[^>]*>', body)
        self.assertTrue(cells)
        self.assertEqual([c for c in cells if 'hide-sm' in c], [])
        self.assertIn("matchMedia('(max-width: 639px)')", body)

    def test_rows_cost_no_extra_queries(self):
        hold_app_settings(self)
        category = Category.objects.create(name='Qzcount', slug='qzcount')
        collection = Collection.objects.create(name='Qzcountcoll', slug='qzcountcoll')

        def add(slug):
            product = _product(slug, category=category)
            product.additional_categories.add(category)
            product.collections.add(collection)

        def queries() -> int:
            # A product save clears the query caches, so warm them again first.
            self._body()
            with CaptureQueriesContext(connection) as captured:
                self._body()
            return len(captured)

        add('count0')
        few = queries()
        for i in range(1, 6):
            add(f'count{i}')
        many = queries()

        self.assertEqual(many, few)
