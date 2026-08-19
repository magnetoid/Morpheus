"""Pagination: page 2 is a page, page 1 is the category, page 900 is not.

The bug these guard was live and unbounded, and it had two independent causes
that produced the identical symptom — 200 OK, page 1's products, and a canonical
naming *itself*, once per integer anyone cared to append:

* Django's paginator **clamps** an out-of-range number back to page 1, so every
  paginated listing served page 1 under any number past the end;
* and a listing with **no paginator at all** ignored `?page=` entirely while the
  canonical echoed it anyway — which is what `/shop/` was doing in production,
  and which no view-level fix could have reached.

Hence both a view fix (out of range is a 404) and a canonical fix (`?page=` is
only trusted when a real paginator says so).
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.rules import page_one_redirect_target, paginated_title


class _FakePage:
    def __init__(self, number):
        self.number = number


class PageOneRedirectTests(TestCase):
    """A listing and that listing `?page=1` are one page under two names."""

    def setUp(self):
        self.client = Client()

    def test_page_one_is_redirected_away(self):
        response = self.client.get('/products/', {'page': '1'})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/products/')

    def test_the_rest_of_the_query_survives_the_redirect(self):
        """Dropping a campaign tag on the way through would break attribution
        for every link that was ever shared."""
        response = self.client.get('/products/?page=1&utm_source=news&sort=price')
        self.assertEqual(response.status_code, 301)
        self.assertIn('utm_source=news', response['Location'])
        self.assertIn('sort=price', response['Location'])
        self.assertNotIn('page=', response['Location'])

    def test_a_real_page_number_is_left_alone(self):
        self.assertEqual(page_one_redirect_target(_request('/products/?page=2')), '')

    def test_every_spelling_of_page_one_collapses(self):
        """A paginator reads `int(value)`; `?page=01` is page 1 wearing a hat."""
        for spelling in ('1', '01', '001', '+1', ' 1 '):
            with self.subTest(page=spelling):
                target = page_one_redirect_target(_request(f'/products/?page={spelling}'))
                self.assertEqual(target, '/products/')

    def test_a_page_value_that_is_not_a_number_is_left_for_the_view(self):
        """Redirecting it would hide the 404 the view is right to return."""
        self.assertEqual(page_one_redirect_target(_request('/products/?page=abc')), '')

    def test_a_url_with_no_page_parameter_is_left_alone(self):
        self.assertEqual(page_one_redirect_target(_request('/products/?sort=price')), '')

    def test_a_post_is_never_redirected(self):
        """A 301 would turn a form submission into a GET and lose the body."""
        request = _request('/products/?page=1')
        request.method = 'POST'
        self.assertEqual(page_one_redirect_target(request), '')


class OutOfRangePageTests(TestCase):
    """A page that is not there gets the same answer as any other URL that is
    not there."""

    @classmethod
    def setUpTestData(cls):
        for i in range(3):
            Product.objects.create(
                name=f'Paged {i}',
                slug=f'paged-{i}',
                sku=f'PG-{i}',
                status='active',
                price=Money(Decimal('10.00'), 'USD'),
            )

    def test_a_page_past_the_end_is_a_404(self):
        self.assertEqual(self.client.get('/products/', {'page': '999'}).status_code, 404)

    def test_a_page_number_that_is_not_a_number_is_a_404(self):
        self.assertEqual(self.client.get('/products/', {'page': 'abc'}).status_code, 404)

    def test_the_first_page_still_renders(self):
        self.assertEqual(self.client.get('/products/').status_code, 200)

    def test_an_empty_listing_still_renders(self):
        """Page 1 of nothing is a page — an empty category must not 404."""
        Product.objects.all().delete()
        self.assertEqual(self.client.get('/products/').status_code, 200)

    def test_an_out_of_range_page_is_not_logged_as_a_broken_url(self):
        """The 404 log records `path_info` with the query stripped, so this 404
        would be filed as a broken `/products/` — a URL that answers 200 — in
        the merchant's own list of addresses to redirect. It is a page number
        past the end, not an address that stopped working."""
        from plugins.installed.seo.models import NotFoundLog

        self.client.get('/products/', {'page': '999'})
        self.assertFalse(NotFoundLog.objects.filter(path='/products/').exists())

    def test_a_genuinely_missing_url_is_still_logged(self):
        from plugins.installed.seo.models import NotFoundLog

        self.client.get('/no-such-page-at-all/')
        self.assertTrue(NotFoundLog.objects.filter(path='/no-such-page-at-all/').exists())

    def test_a_category_page_past_the_end_is_a_404_too(self):
        from plugins.installed.catalog.models import Category

        category = Category.objects.create(name='Paged Cat', slug='paged-cat')
        url = reverse('storefront:category_detail', kwargs={'slug': category.slug})
        self.assertEqual(self.client.get(url, {'page': '999'}).status_code, 404)


class RenderedPageTwoTests(TestCase):
    """The whole chain, on a real second page.

    The canonical now depends on the view's paginator reaching the head builder
    (`page_obj` → `SeoPage` → `canonical_for`). If that link ever breaks, page 2
    silently canonicalises onto page 1 and every product past the first screen
    stops having a home — a de-indexing with no error, no log line and no
    visible difference in a browser. This is the test that would notice.
    """

    @classmethod
    def setUpTestData(cls):
        Product.objects.bulk_create(
            [
                Product(
                    name=f'Page Two {i}',
                    slug=f'page-two-{i}',
                    sku=f'P2-{i}',
                    status='active',
                    price=Money(Decimal('9.00'), 'USD'),
                )
                for i in range(61)  # the PLP paginates at 60
            ]
        )

    def _head(self, url: str) -> str:
        body = self.client.get(url).content.decode()
        return body.split('</head>')[0]

    def _canonical(self, url: str) -> str:
        match = re.search(r'<link rel="canonical" href="([^"]+)"', self._head(url))
        return match.group(1) if match else ''

    def test_page_two_is_canonical_to_itself(self):
        self.assertTrue(self._canonical('/products/?page=2').endswith('/products/?page=2'))

    def test_page_two_carries_its_own_title(self):
        self.assertIn('Page 2', self._head('/products/?page=2'))

    def test_page_two_is_still_indexable(self):
        self.assertNotIn('noindex', self._head('/products/?page=2'))

    def test_page_one_is_canonical_to_the_clean_url(self):
        """`rel=next` still names page 2 — it is the canonical that must not."""
        self.assertTrue(self._canonical('/products/').endswith('/products/'))

    def test_rel_prev_from_page_two_names_the_clean_url(self):
        """Not `?page=1`, which we would immediately 301 — a wasted hop for
        every crawler that follows it."""
        head = self._head('/products/?page=2')
        match = re.search(r'<link rel="prev" href="([^"]+)"', head)
        self.assertIsNotNone(match, 'page 2 should carry a rel=prev link')
        self.assertTrue(match.group(1).endswith('/products/'))


class PaginatedTitleTests(TestCase):
    """Every page of a listing otherwise carries the category's title, so an
    engine sees a dozen identically-titled pages and picks one."""

    def test_page_two_gets_its_own_title(self):
        self.assertEqual(paginated_title('Shop', _FakePage(2)), 'Shop — Page 2')

    def test_page_one_is_the_category(self):
        self.assertEqual(paginated_title('Shop', _FakePage(1)), 'Shop')

    def test_no_paginator_changes_nothing(self):
        self.assertEqual(paginated_title('Shop', None), 'Shop')


def _request(url: str):
    from django.test import RequestFactory

    return RequestFactory().get(url)
