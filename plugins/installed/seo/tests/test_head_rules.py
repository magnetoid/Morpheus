"""The rules a page's head obeys once it is NOT an ordinary indexable page (v0.80.0).

A live crawl of all three stores (Oct 2026) found every 404 answering with the
right status and the right `noindex` — and then, in the same head, a canonical
naming the dead URL (or, for `?page=999`, naming the live listing), hreflang
alternates in two languages pointing at that same dead URL, an `og:url`, and a
WebPage graph. Each tag is valid on its own; together they describe a page that
does not exist. Same shape on every `noindex` page, and on every page with a
tracking parameter, whose hreflang echoed `?utm_source=` while the canonical had
already stripped it.

The rules:

* an error page carries a title, a description and `noindex, follow` — nothing
  that names a URL or describes an entity;
* a `noindex` page never names another URL: no hreflang, no prev/next, no
  graph, and a canonical only when the canonical IS the page;
* hreflang is derived from the canonical, never from the request;
* a market alternate exists only for a market that names its countries and
  whose `?market=` is an indexable parameter.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

_TWO_LANGUAGES = {'LANGUAGES': [('en', 'English'), ('sr', 'Srpski')], 'LANGUAGE_CODE': 'en'}

_TITLE = re.compile(r'<title[^>]*>(.*?)</title>', re.I | re.S)
_ROBOTS = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
_CANONICAL = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', re.I)
_ALTERNATE = re.compile(r'<link[^>]+rel="alternate"[^>]+href="([^"]*)"[^>]+hreflang="([^"]+)"')


def _head(response) -> str:
    return response.content.decode().split('</head>', 1)[0]


def _alternates(head: str) -> dict[str, str]:
    return {code: href.replace('&amp;', '&') for href, code in _ALTERNATE.findall(head)}


def _graph(head: str) -> list[dict]:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    nodes: list[dict] = []
    for block in blocks:
        nodes.extend(json.loads(block).get('@graph', []))
    return nodes


def _product(slug: str, **extra):
    from plugins.installed.catalog.models import Product

    return Product.objects.create(
        name=extra.pop('name', slug.replace('-', ' ').title()),
        slug=slug,
        sku=slug.upper()[:30],
        price=Money(Decimal('12.00'), 'USD'),
        product_type='simple',
        status='active',
        **extra,
    )


class ErrorPageHeadTests(TestCase):
    """A 404 is not a page: title, description, robots — and nothing else."""

    def setUp(self):
        cache.clear()

    def _assert_bare_error_head(self, path: str) -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404, path)
        head = _head(response)
        self.assertEqual(len(_TITLE.findall(head)), 1, f'{path}: <title> count')
        self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'], f'{path}: robots')
        self.assertIsNone(_CANONICAL.search(head), f'{path}: an error page names a canonical')
        self.assertNotIn('hreflang=', head, f'{path}: an error page declares alternates')
        self.assertNotIn('application/ld+json', head, f'{path}: an error page has a graph')
        self.assertNotIn('og:url', head, f'{path}: an error page publishes og:url')
        self.assertNotIn('rel="next"', head)
        self.assertNotIn('rel="prev"', head)
        return head

    @override_settings(**_TWO_LANGUAGES)
    def test_missing_pages_in_every_language_carry_a_bare_head(self):
        for path in (
            '/no-such-page-anywhere/',
            '/sr/no-such-page-anywhere/',
            '/products/no-such-product-anywhere/',
            '/category/no-such-category-anywhere/',
        ):
            with self.subTest(path=path):
                self._assert_bare_error_head(path)

    def test_a_page_number_past_the_end_names_no_live_listing(self):
        # Before: `/products/?page=999` answered 404 with a canonical naming
        # `/products/` — "this dead URL is that live page", twice over.
        self._assert_bare_error_head('/products/?page=999')

    @override_settings(**_TWO_LANGUAGES)
    def test_the_error_title_follows_the_language(self):
        english = _TITLE.search(_head(self.client.get('/no-such-page-anywhere/'))).group(1)
        serbian = _TITLE.search(_head(self.client.get('/sr/no-such-page-anywhere/'))).group(1)
        self.assertTrue(english.startswith('Page not found'), english)
        self.assertTrue(serbian.startswith('Stranica nije pronađena'), serbian)


@override_settings(**_TWO_LANGUAGES)
class NoindexPageHeadTests(TestCase):
    """A page that asks not to be indexed never names another URL."""

    def setUp(self):
        cache.clear()

    def test_a_private_page_keeps_its_own_canonical_and_nothing_else(self):
        head = _head(self.client.get('/cart/'))
        self.assertEqual(_ROBOTS.findall(head), ['noindex, nofollow'])
        self.assertEqual(_CANONICAL.findall(head), ['http://testserver/cart/'])
        self.assertEqual(_alternates(head), {})
        self.assertNotIn('application/ld+json', head)

    def test_internal_search_results_are_noindex_without_a_foreign_canonical(self):
        _product('searchable-thing', name='Searchable thing')
        for path in ('/products/?q=searchable', '/products/?q=searchable&utm_source=mail'):
            with self.subTest(path=path):
                head = _head(self.client.get(path))
                self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'])
                self.assertIsNone(_CANONICAL.search(head), 'canonical names /products/')
                self.assertEqual(_alternates(head), {})
                self.assertNotIn('application/ld+json', head)

    def test_a_merchant_noindex_reason_from_the_view_is_honoured(self):
        from plugins.installed.seo.pages.resolve import resolve_page

        request = self.client.get('/about/').wsgi_request
        page = resolve_page(request, {'seo_noindex_reason': 'placeholder page'})
        self.assertTrue(page.noindex)
        self.assertIn('placeholder page', page.reason)


class EmptyListingTests(TestCase):
    """An empty listing is a soft 404: kept out of the index, links still followed."""

    def setUp(self):
        cache.clear()

    def test_an_empty_catalogue_is_noindex_follow(self):
        head = _head(self.client.get('/products/'))
        self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'])
        # No query string, so the canonical is the page itself and may stay.
        self.assertEqual(_CANONICAL.findall(head), ['http://testserver/products/'])

    def test_a_listing_with_items_is_indexable(self):
        _product('one-thing-on-the-shelf')
        robots = _ROBOTS.findall(_head(self.client.get('/products/')))
        self.assertEqual(len(robots), 1)
        self.assertTrue(robots[0].startswith('index, follow'), robots)

    def test_a_view_reported_count_of_zero_holds_a_listing_back(self):
        from plugins.installed.seo.pages.resolve import resolve_page

        # A listing route whose view reports what it shows; the count it states
        # wins over anything the resolver could infer.
        request = self.client.get('/products/').wsgi_request
        page = resolve_page(request, {'seo_item_count': 0})
        self.assertTrue(page.noindex)
        self.assertIn('empty listing', page.reason)

    def test_an_unreported_count_changes_nothing(self):
        from plugins.installed.seo.pages.resolve import resolve_page

        request = self.client.get('/about/').wsgi_request
        self.assertFalse(resolve_page(request, {}).noindex)


@override_settings(**_TWO_LANGUAGES)
class AlternatesFollowTheCanonicalTests(TestCase):
    """hreflang names the canonical in each language — never the raw request."""

    def setUp(self):
        cache.clear()

    def test_tracking_parameters_never_reach_an_alternate(self):
        _product('anything-at-all')
        head = _head(self.client.get('/?utm_source=newsletter&fbclid=abc'))
        alternates = _alternates(head)
        self.assertEqual(set(alternates), {'en', 'sr', 'x-default'})
        self.assertEqual(alternates['en'], 'http://testserver/')
        self.assertEqual(alternates['sr'], 'http://testserver/sr/')
        self.assertEqual(alternates['x-default'], 'http://testserver/')

    def test_page_two_keeps_its_page_in_every_language(self):
        for n in range(61):
            _product(f'paged-product-{n:02d}')
        head = _head(self.client.get('/products/?page=2&utm_campaign=x'))
        alternates = _alternates(head)
        self.assertEqual(alternates['en'], 'http://testserver/products/?page=2')
        self.assertEqual(alternates['sr'], 'http://testserver/sr/products/?page=2')

    def test_the_graph_describes_the_canonical_url(self):
        _product('graph-subject')
        head = _head(self.client.get('/?utm_source=newsletter'))
        webpage = next(n for n in _graph(head) if n.get('@id', '').endswith('#webpage'))
        self.assertEqual(webpage['url'], 'http://testserver/')


class MarketAlternateTests(TestCase):
    """A market is a region; its alternate must name a page that exists on its own."""

    def setUp(self):
        cache.clear()
        _product('market-probe')

    def _market(self, **extra):
        from plugins.installed.markets.models import Market

        defaults = {
            'code': 'eu',
            'label': 'Europe',
            'currency': 'EUR',
            'default_locale': 'en',
            'country_codes': [],
            'is_active': True,
        }
        defaults.update(extra)
        return Market.objects.create(**defaults)

    def test_a_market_without_countries_publishes_no_alternate(self):
        # dotbooks: market "eu", locale en, no countries → every page said
        # `hreflang="en" → /?market=eu`, a URL whose canonical is `/`.
        self._market()
        self.assertEqual(_alternates(_head(self.client.get('/'))), {})

    def test_a_market_whose_parameter_is_consolidated_publishes_no_alternate(self):
        self._market(country_codes=['DE', 'FR'])
        self.assertEqual(_alternates(_head(self.client.get('/'))), {})

    def test_an_indexable_market_publishes_regional_alternates_and_one_default(self):
        from plugins.installed.seo.models import IndexRule
        from plugins.installed.seo.rules import invalidate_index_rules_cache

        self._market(country_codes=['DE', 'FR'])
        IndexRule.objects.create(param='market', policy='allowlist', allowed_values=['eu'])
        invalidate_index_rules_cache()
        clean = _alternates(_head(self.client.get('/')))
        regional = _alternates(_head(self.client.get('/?market=eu')))
        self.assertEqual(clean['en-DE'], 'http://testserver/?market=eu')
        self.assertEqual(clean['en-FR'], 'http://testserver/?market=eu')
        # One x-default for the whole cluster: the clean URL, from both members.
        self.assertEqual(clean['x-default'], 'http://testserver/')
        self.assertEqual(regional['x-default'], 'http://testserver/')


class PageKindTableTests(TestCase):
    """Route names are matched with their namespace: `home` is not one route."""

    def test_another_apps_route_named_home_is_not_the_home_page(self):
        from django.urls import ResolverMatch

        from plugins.installed.seo.pages.resolve import resolve_page

        request = self.client.get('/about/').wsgi_request
        request.resolver_match = ResolverMatch(
            lambda r: None, (), {}, url_name='home', app_names=['wishlist'], namespaces=['wishlist']
        )
        self.assertNotEqual(resolve_page(request, {}).kind, 'home')

    def test_the_storefront_home_is_the_home_page(self):
        from plugins.installed.seo.pages.resolve import resolve_page

        request = self.client.get('/').wsgi_request
        self.assertEqual(resolve_page(request, {}).kind, 'home')


class SignInTitleTests(TestCase):
    """Auth pages are named for a person, not after their route."""

    def test_the_sign_in_page_says_sign_in(self):
        title = _TITLE.search(_head(self.client.get('/auth/login/'))).group(1)
        self.assertTrue(title.startswith('Sign in'), title)
