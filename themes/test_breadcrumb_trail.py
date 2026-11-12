"""A breadcrumb is one list, rendered twice (v0.161.0).

The trail a shopper sees and the head's BreadcrumbList both come from the view's
`breadcrumb_items` (`{% breadcrumb_trail %}`, storefront/templatetags/breadcrumbs.py).
Before, every product page's markup named the `/products/?category=<slug>` filter
address, which canonicalises to `/products/`, while the visible trail linked
`/category/<slug>/` or `/genre/<slug>/`, labelled the catalogue differently and
left out the product. These tests parse both renderings and compare them, under
each catalogue theme. The travel themes are covered in
booking_marketplace/tests/test_breadcrumb_trail.py, which reuses the readers here.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from decimal import Decimal
from urllib.parse import urlsplit

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from themes.registry import theme_registry

_NAV = re.compile(r'<nav\b[^>]*>(.*?)</nav>', re.S | re.I)
_LI = re.compile(r'<li\b[^>]*>(.*?)</li>', re.S | re.I)
_HREF = re.compile(r'<a\b[^>]*\bhref="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
_CURRENT = re.compile(r'<span\b[^>]*aria-current="page"[^>]*>(.*?)</span>', re.S | re.I)
_TAG = re.compile(r'<[^>]+>')
_LDJSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


def _text(fragment: str) -> str:
    return ' '.join(html_lib.unescape(_TAG.sub('', fragment)).split())


def visible_trail(page: str) -> list[tuple[str, str | None]]:
    """[(name, href)] of the page's one breadcrumb trail; the current page has href None.

    The trail is the `<nav>` whose list ends in an `aria-current="page"` item (the
    shared partial and every theme's override render it that way).
    """
    body = page.split('</head>', 1)[-1]
    trails = [
        m.group(1)
        for m in _NAV.finditer(body)
        if m.group(1).lstrip().lower().startswith('<ol') and _CURRENT.search(m.group(1))
    ]
    if len(trails) != 1:
        raise AssertionError(f'expected one breadcrumb trail, found {len(trails)}')
    items = []
    for li in _LI.findall(trails[0]):
        link = _HREF.search(li)
        if link:
            items.append((_text(link.group(2)), html_lib.unescape(link.group(1))))
        else:
            current = _CURRENT.search(li)
            items.append((_text(current.group(1) if current else li), None))
    return items


def markup_trail(page: str) -> list[tuple[str, str]]:
    """[(name, item url)] of the head's one BreadcrumbList."""
    lists = []
    for block in _LDJSON.findall(page):
        data = json.loads(block)
        for node in data.get('@graph', [data]) if isinstance(data, dict) else data:
            if isinstance(node, dict) and node.get('@type') == 'BreadcrumbList':
                lists.append(node)
    if len(lists) != 1:
        raise AssertionError(f'expected one BreadcrumbList, found {len(lists)}')
    elements = sorted(lists[0]['itemListElement'], key=lambda e: e['position'])
    return [(e['name'], e.get('item', '')) for e in elements]


def _address(url: str) -> str:
    parts = urlsplit(url)
    return parts.path + (f'?{parts.query}' if parts.query else '')


def assert_one_trail(testcase, page: str) -> list[tuple[str, str | None]]:
    """The visible trail equals the BreadcrumbList: same names, same links, in order."""
    shown = visible_trail(page)
    marked = markup_trail(page)
    testcase.assertEqual([n for n, _h in shown], [n for n, _u in marked])
    for (name, href), (_n, url) in zip(shown[:-1], marked[:-1], strict=True):
        testcase.assertIsNotNone(href, f'{name}: only the page itself is unlinked')
        testcase.assertEqual(_address(href), _address(url), name)
    testcase.assertIsNone(shown[-1][1], 'the page itself is the last item, not a link')
    for _name, url in marked:
        testcase.assertNotIn('?category=', url)
    return shown


class _CatalogueTrailTests:
    theme = ''

    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Product

        cls.parent = Category.objects.create(name='Trail Parent', slug='trail-parent')
        cls.child = Category.objects.create(
            name='Trail Child', slug='trail-child', parent=cls.parent
        )
        for slug, category in (('trail-probe', cls.child), ('trail-book', cls.child)):
            Product.objects.create(
                name=slug.replace('-', ' ').title(),
                slug=slug,
                sku=slug.upper(),
                price=Money(Decimal('9.00'), 'USD'),
                product_type='simple',
                status='active',
                category=category,
            )

    def setUp(self):
        cache.clear()
        override = override_settings(MORPHEUS_ACTIVE_THEME=self.theme)
        override.enable()
        self.addCleanup(override.disable)
        previous = theme_registry._active_name
        theme_registry.set_active(self.theme)
        self.addCleanup(setattr, theme_registry, '_active_name', previous)

    def _page(self, path):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, 200, path)
        return resp.content.decode()

    def _catalogue(self):
        from plugins.installed.storefront.services import catalogue_label

        return catalogue_label()

    def test_the_product_page_shows_the_trail_it_marks_up(self):
        shown = assert_one_trail(self, self._page('/products/trail-probe/'))
        self.assertEqual(
            shown,
            [
                ('Home', '/'),
                (self._catalogue(), '/products/'),
                ('Trail Parent', '/category/trail-parent/'),
                ('Trail Child', '/category/trail-child/'),
                ('Trail Probe', None),
            ],
        )

    def test_the_product_crumb_keeps_its_url_in_the_markup(self):
        marked = markup_trail(self._page('/products/trail-probe/'))
        self.assertEqual(_address(marked[-1][1]), '/products/trail-probe/')

    def test_a_book_with_a_genre_sits_under_the_genre_page(self):
        from plugins.installed.book_product.models import BookProduct, Genre
        from plugins.installed.catalog.models import Product

        genre = Genre.objects.create(name='Trail Genre', slug='trail-genre')
        book = BookProduct.objects.create(product=Product.objects.get(slug='trail-book'))
        book.genres.add(genre)
        shown = assert_one_trail(self, self._page('/products/trail-book/'))
        self.assertEqual(shown[2], ('Trail Genre', '/genre/trail-genre/'))
        self.assertEqual(len(shown), 4)

    def test_the_category_page_lists_its_parents(self):
        shown = assert_one_trail(self, self._page('/category/trail-child/'))
        self.assertEqual(
            shown,
            [
                ('Home', '/'),
                (self._catalogue(), '/products/'),
                ('Trail Parent', '/category/trail-parent/'),
                ('Trail Child', None),
            ],
        )

    def test_a_filtered_shelf_names_the_category_page(self):
        shown = assert_one_trail(self, self._page('/products/?category=trail-child'))
        self.assertEqual([h for _n, h in shown[2:]], ['/category/trail-parent/', None])
        self.assertEqual(shown[-1][0], 'Trail Child')


class DotBooksTrailTests(_CatalogueTrailTests, TestCase):
    theme = 'dot_books'


class SupernaturalTrailTests(_CatalogueTrailTests, TestCase):
    theme = 'supernatural_shop'


class IrvingTrailTests(_CatalogueTrailTests, TestCase):
    theme = 'irving_survival'
