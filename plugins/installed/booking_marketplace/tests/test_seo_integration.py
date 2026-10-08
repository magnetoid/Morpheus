"""The travel marketplace's pages as the platform sees them (v0.80.0).

Each test is a defect a crawl of montenegro-experience.me found live:

* every host page read "0 listings" (171 of them, all in the sitemap) because
  the shell counted catalog Products and the hosts' offers live here;
* booking pages carried two or three JSON-LD blocks — the head's, this app's,
  and on the listings a FAQPage whose questions the page never showed;
* `/shop/` was headed "Experiences in Montenegro";
* a deactivated host's experiences and hotels still answered 200;
* a search sent every visitor to the empty product grid.
"""

from __future__ import annotations

import json
import re

from django.core.cache import cache
from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Property
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

_ROBOTS = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
_LDJSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _head(response) -> str:
    return response.content.decode().split('</head>', 1)[0]


def _host(slug='kotor-boats', **kw):
    return Vendor.objects.create(name=slug.replace('-', ' ').title(), slug=slug, **kw)


def _experience(vendor, slug, **kw):
    defaults = {
        'name': slug.replace('-', ' ').title(),
        'short_description': 'Out on the water.',
        'description': 'A longer description.',
        'price': Money(60, 'EUR'),
        'listing_kind': 'experience',
        'is_active': True,
        'region': 'kotor',
    }
    defaults.update(kw)
    return BookableService.objects.create(vendor=vendor, slug=slug, **defaults)


class HostPageTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def test_a_host_page_lists_the_hosts_experiences_and_stays(self):
        host = _host()
        _experience(host, 'bay-kayak', name='Bay Kayak')
        Property.objects.create(vendor=host, name='Old Town Rooms', slug='old-town-rooms')
        response = self.client.get('/vendor/kotor-boats/')
        body = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('/bookings/bay-kayak/', body)
        self.assertIn('/hotels/old-town-rooms/', body)
        self.assertNotIn('no active listings', body)
        robots = _ROBOTS.findall(_head(response))
        self.assertTrue(robots and robots[0].startswith('index'), robots)

    def test_a_host_with_nothing_to_offer_stays_out_of_the_index(self):
        _host('quiet-host')
        head = _head(self.client.get('/vendor/quiet-host/'))
        self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'])

    def test_the_directory_and_the_sitemap_count_the_hosts_offers(self):
        from plugins.installed.catalog.vendors import listing_counts

        host = _host()
        _experience(host, 'bay-kayak')
        _experience(host, 'bay-sunset')
        self.assertEqual(listing_counts().get(str(host.pk)), 2)
        self.assertIn('/vendor/kotor-boats/', self.client.get('/vendors/').content.decode())

    def test_the_page_is_titled_for_hosts_not_publishers(self):
        _experience(_host(), 'bay-kayak')
        title = re.search(r'<title>(.*?)</title>', _head(self.client.get('/vendor/kotor-boats/')))
        self.assertIn('Hosts', title.group(1))
        self.assertNotIn('Publishers', title.group(1))


class OneGraphPerPageTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def _graph(self, path):
        blocks = _LDJSON.findall(self.client.get(path).content.decode())
        self.assertEqual(len(blocks), 1, f'{path}: {len(blocks)} JSON-LD blocks')
        return json.loads(blocks[0])['@graph']

    def test_an_experience_page_has_one_graph_with_its_product(self):
        _experience(_host(), 'bay-kayak')
        graph = self._graph('/bookings/bay-kayak/')
        types = [n.get('@type') for n in graph]
        self.assertIn('Product', types)
        self.assertEqual(types.count('BreadcrumbList'), 1)
        webpage = next(n for n in graph if n.get('@id', '').endswith('#webpage'))
        self.assertEqual(
            webpage['mainEntity']['@id'], 'http://testserver/bookings/bay-kayak/#product'
        )

    def test_listings_publish_no_faq_the_page_does_not_show(self):
        _experience(_host(), 'bay-kayak')
        for path in ('/bookings/', '/shop/'):
            with self.subTest(path=path):
                body = self.client.get(path).content.decode()
                self.assertNotIn('FAQPage', body)

    def test_the_hotels_index_faq_is_the_one_on_the_page(self):
        Property.objects.create(vendor=_host(), name='Old Town Rooms', slug='old-town-rooms')
        response = self.client.get('/hotels/')
        graph = json.loads(_LDJSON.findall(response.content.decode())[0])['@graph']
        faq = next(n for n in graph if n.get('@type') == 'FAQPage')
        for question in faq['mainEntity']:
            self.assertIn(question['name'], response.content.decode().split('</head>', 1)[1])


class ListingRulesTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        cache.clear()

    def test_a_search_of_the_experiences_is_noindex(self):
        _experience(_host(), 'bay-kayak')
        head = _head(self.client.get('/bookings/?q=kayak'))
        self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'])

    def test_a_region_with_nothing_to_book_is_noindex_and_left_off_the_index(self):
        _experience(_host(), 'bay-kayak', region='kotor')
        head = _head(self.client.get('/regions/ulcinj/'))
        self.assertEqual(_ROBOTS.findall(head), ['noindex, follow'])
        index = self.client.get('/regions/').content.decode()
        self.assertIn('/regions/kotor/', index)
        self.assertNotIn('/regions/ulcinj/', index)

    def test_the_hosts_back_office_is_private(self):
        from django.urls import resolve

        from plugins.installed.booking_marketplace.seo import on_seo_resolve_page

        request = self.client.get('/').wsgi_request
        request.resolver_match = resolve('/bookings/host/')
        page = on_seo_resolve_page(None, request=request, context={})
        self.assertEqual(page.kind, 'private')
        self.assertTrue(page.noindex)

    def test_the_shop_is_headed_as_a_shop(self):
        _experience(_host(), 'olive-oil', listing_kind='product', name='Olive Oil')
        body = self.client.get('/shop/').content.decode()
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.S).group(1)
        self.assertIn('Shop Montenegro', h1)
        self.assertNotIn('Experiences', h1)


class RegionDescriptionTests(MontenegroThemeMixin, TestCase):
    """The region pages joined the sitemap in v0.80.0 with no meta description.

    A crawl after the deploy found all ten of them without one — the only
    indexable pages on the store missing it. The description is built from what
    the page lists, so it can never describe a region the page does not show.
    """

    _DESCRIPTION = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)

    def setUp(self):
        cache.clear()

    def _description(self, path) -> str:
        import html

        found = self._DESCRIPTION.findall(_head(self.client.get(path)))
        self.assertEqual(len(found), 1, f'{path}: {found}')
        return html.unescape(found[0])

    def test_a_region_page_describes_what_it_lists(self):
        host = _host()
        _experience(host, 'bay-kayak', name='Bay Kayak', region='kotor')
        _experience(host, 'perast-boat', name='Perast Boat', region='kotor')
        _experience(host, 'budva-sail', name='Budva Sail', region='budva')
        description = self._description('/regions/kotor/')
        self.assertIn('Kotor Bay', description)
        self.assertIn('2 experiences', description)
        self.assertIn('Bay Kayak', description)
        self.assertNotIn('Budva Sail', description)

    def test_a_long_region_description_stays_snippet_length(self):
        host = _host()
        for i in range(12):
            _experience(
                host,
                f'long-experience-{i}',
                name=f'A Very Long Experience Name Number {i} Above the Bay',
                region='kotor',
            )
        description = self._description('/regions/kotor/')
        self.assertLessEqual(len(description), 160, description)
        self.assertIn('12 experiences', description)

    def test_the_regions_index_names_the_regions_it_lists(self):
        host = _host()
        _experience(host, 'bay-kayak', region='kotor')
        _experience(host, 'budva-sail', region='budva')
        description = self._description('/regions/')
        self.assertIn('Kotor Bay', description)
        self.assertIn('Budva Riviera', description)
        self.assertNotIn('Lake Skadar', description)


@override_settings(LANGUAGES=[('en', 'English'), ('sr', 'Srpski')], LANGUAGE_CODE='en')
class SerbianChromeTests(MontenegroThemeMixin, TestCase):
    """The header menu and region names were English on every `/sr/` page."""

    def test_the_menu_counts_are_translated(self):
        from django.utils import translation

        from plugins.installed.booking_marketplace.context_processors import _nav_categories
        from plugins.installed.catalog.models import Category

        category = Category.objects.create(name='Sea Trips', slug='sea-trips')
        host = _host()
        _experience(host, 'bay-kayak', category=category)
        _experience(host, 'bay-sail', category=category)
        with translation.override('sr'):
            tiles = _nav_categories()
        self.assertEqual(
            next(t for t in tiles if t['label'] == 'Sea Trips')['desc'], '2 doživljaja'
        )

    def test_region_names_are_translated(self):
        from django.utils import translation

        _experience(_host(), 'bay-kayak', region='kotor')
        with translation.override('sr'):
            self.assertEqual(
                BookableService.objects.get(slug='bay-kayak').get_region_display(), 'Boka Kotorska'
            )
        body = self.client.get('/sr/regions/').content.decode()
        self.assertIn('Boka Kotorska', body)
        self.assertNotIn('Kotor Bay', body.split('</head>', 1)[1])


class InactiveHostTests(MontenegroThemeMixin, TestCase):
    def test_a_deactivated_hosts_pages_are_gone(self):
        host = _host(is_active=False)
        _experience(host, 'gone-kayak')
        Property.objects.create(vendor=host, name='Gone Rooms', slug='gone-rooms')
        self.assertEqual(self.client.get('/bookings/gone-kayak/').status_code, 404)
        self.assertEqual(self.client.get('/hotels/gone-rooms/').status_code, 404)


class SearchPathTests(TestCase):
    def test_search_lands_on_the_experiences_when_they_are_the_inventory(self):
        _experience(_host(), 'bay-kayak')
        response = self.client.get('/search/?q=kayak')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/bookings/?q=kayak')

    def test_a_store_with_a_catalogue_keeps_its_own_search(self):
        from decimal import Decimal

        from plugins.installed.catalog.models import Product

        _experience(_host(), 'bay-kayak')
        Product.objects.create(
            name='Guidebook',
            slug='guidebook',
            sku='GUIDE-1',
            price=Money(Decimal('12.00'), 'USD'),
            product_type='simple',
            status='active',
        )
        self.assertEqual(self.client.get('/search/?q=kayak')['Location'], '/products/?q=kayak')
