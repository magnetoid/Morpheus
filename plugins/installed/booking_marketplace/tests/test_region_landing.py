"""Region landing pages and the region × category pages below them (v0.161.0).

"Kotor boat tours" had no page: `/bookings/?region=kotor&category=boat-tours` lists
them under a canonical of bare `/bookings/`. `/regions/<key>/<category>/` lists the
region's live experiences in the category's subtree with the region's geography and
the category's own text above them; the region page gained its text, its hotels,
places and upcoming events, and chips to those pages; `/bookings/` filtered to a
region (and a category) names the landing page as its canonical; the sitemap lists
each pair with an experience on it.
"""

from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone, translation
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Event, Place, Property
from plugins.installed.booking_marketplace.sitemap import contribute_sitemap_urls
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from themes.test_breadcrumb_trail import assert_one_trail

_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]*)"')
_ROBOTS = re.compile(r'<meta name="robots" content="([^"]*)"')
_TITLE = re.compile(r'<title>(.*?)</title>', re.S)
_LDJSON = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)


class _LandingFixtures:
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Category, Vendor

        host = Vendor.objects.create(name='Bay Host', slug='bay-host', is_active=True)
        gone = Vendor.objects.create(name='Gone Host', slug='gone-host', is_active=False)
        cls.water = Category.objects.create(
            name='Water Fun', slug='water-fun', description='Everything on the water.'
        )
        cls.boats = Category.objects.create(name='Boat Tours', slug='boat-tours', parent=cls.water)
        cls.hiking = Category.objects.create(name='Hiking', slug='hiking')
        cls.closed = Category.objects.create(name='Closed', slug='closed', is_active=False)

        def listing(slug, region, category, vendor=host, kind='experience'):
            return BookableService.objects.create(
                vendor=vendor,
                name=slug.replace('-', ' ').title(),
                slug=slug,
                listing_kind=kind,
                region=region,
                category=category,
                price=Money(Decimal('40'), 'EUR'),
                is_active=True,
            )

        listing('kotor-boat', 'kotor', cls.boats)
        listing('kotor-hike', 'kotor', cls.hiking)
        listing('budva-boat', 'budva', cls.boats)
        listing('kotor-ghost', 'kotor', cls.hiking, vendor=gone)
        listing('budva-honey', 'budva', cls.hiking, kind='product')
        listing('kotor-closed', 'kotor', cls.closed)

        Property.objects.create(
            vendor=host, name='Bay Rooms', slug='bay-rooms', region='kotor', is_active=True
        )
        town = Place.objects.create(name='Perast', slug='perast', region='kotor', is_active=True)
        Event.objects.create(name='Boka Night', slug='boka-night', place=town, month=8)
        past = timezone.localdate() - datetime.timedelta(days=30)
        Event.objects.create(
            name='Last Year Regatta',
            slug='last-year-regatta',
            region='kotor',
            is_annual=False,
            start_date=past,
            end_date=past,
        )

    def setUp(self):
        cache.clear()

    def _page(self, path, status=200):
        resp = self.client.get(path)
        self.assertEqual(resp.status_code, status, path)
        return resp.content.decode()


class RegionCategoryPageTests(MontenegroThemeMixin, _LandingFixtures, TestCase):
    def test_it_lists_the_region_and_the_category_subtree_only(self):
        body = self._page('/regions/kotor/water-fun/')
        self.assertIn('/bookings/kotor-boat/', body)
        for other in ('budva-boat', 'kotor-hike', 'kotor-ghost', 'kotor-closed'):
            self.assertNotIn(f'/bookings/{other}/', body, other)

    def test_it_opens_with_the_region_and_the_category_text(self):
        body = self._page('/regions/kotor/water-fun/')
        self.assertIn('The fjord-like Bay of Kotor', body)
        self.assertIn('Everything on the water.', body)
        self.assertIn('Water Fun in Kotor Bay', _TITLE.search(body).group(1))

    def test_its_trail_is_home_regions_region_category(self):
        shown = assert_one_trail(self, self._page('/regions/kotor/boat-tours/'))
        self.assertEqual(
            shown,
            [
                ('Home', '/'),
                ('Regions', '/regions/'),
                ('Kotor Bay', '/regions/kotor/'),
                ('Boat Tours', None),
            ],
        )

    def test_unknown_or_switched_off_is_a_404(self):
        for path in (
            '/regions/atlantis/water-fun/',
            '/regions/kotor/no-such-category/',
            '/regions/kotor/closed/',
        ):
            with self.subTest(path=path):
                self._page(path, status=404)

    def test_an_empty_pair_renders_held_out_of_the_index(self):
        body = self._page('/regions/budva/hiking/')
        self.assertIn('noindex, follow', _ROBOTS.search(body).group(1))
        self.assertNotIn('/bookings/budva-honey/', body)

    def test_a_listed_pair_is_indexable_and_its_own_canonical(self):
        body = self._page('/regions/kotor/water-fun/')
        self.assertTrue(_ROBOTS.search(body).group(1).startswith('index, follow'))
        self.assertEqual(
            _CANONICAL.search(body).group(1), 'http://testserver/regions/kotor/water-fun/'
        )

    def test_a_broad_category_is_paged(self):
        BookableService.objects.create(
            vendor=BookableService.objects.get(slug='kotor-boat').vendor,
            name='Kotor Kayak',
            slug='kotor-kayak',
            listing_kind='experience',
            region='kotor',
            category=self.water,
            price=Money(Decimal('30'), 'EUR'),
            is_active=True,
        )
        with patch('plugins.installed.booking_marketplace.views.LANDING_PER_PAGE', 1):
            first = self._page('/regions/kotor/water-fun/')
            second = self._page('/regions/kotor/water-fun/?page=2')
            self._page('/regions/kotor/water-fun/?page=3', status=404)
        self.assertIn('rel="next"', first)
        shown = {
            slug
            for slug in ('kotor-boat', 'kotor-kayak')
            for body in (first, second)
            if f'/bookings/{slug}/' in body
        }
        self.assertEqual(shown, {'kotor-boat', 'kotor-kayak'})
        self.assertNotEqual('/bookings/kotor-boat/' in first, '/bookings/kotor-boat/' in second)
        self.assertEqual(
            _CANONICAL.search(second).group(1),
            'http://testserver/regions/kotor/water-fun/?page=2',
        )


@serbian_enabled
class RegionCategorySerbianTests(MontenegroThemeMixin, _LandingFixtures, TestCase):
    def test_the_title_is_translated(self):
        body = self._page('/sr/regions/kotor/water-fun/')
        with translation.override('sr'):
            region = str(translation.gettext('Kotor Bay'))
        self.assertEqual(region, 'Boka Kotorska')
        self.assertIn(f'Water Fun — {region}', _TITLE.search(body).group(1))
        self.assertIn('Bokokotorski zaliv nalik fjordu', body)

    def test_only_the_landing_page_declares_its_languages(self):
        self.assertIn('hreflang="sr"', self._page('/regions/kotor/'))
        self.assertNotIn('hreflang=', self._page('/bookings/?region=kotor'))


class RegionPageTests(MontenegroThemeMixin, _LandingFixtures, TestCase):
    def test_the_region_page_opens_with_its_text(self):
        self.assertIn('The fjord-like Bay of Kotor', self._page('/regions/kotor/'))

    def test_hotels_places_and_upcoming_events_show_when_the_region_has_them(self):
        body = self._page('/regions/kotor/')
        for section, row in (
            ('region-hotels', '/hotels/bay-rooms/'),
            ('region-places', '/places/perast/'),
            ('region-events', '/events/boka-night/'),
        ):
            with self.subTest(section=section):
                self.assertIn(f'id="{section}"', body)
                self.assertIn(row, body)
        self.assertNotIn('/events/last-year-regatta/', body)

    def test_a_region_without_them_shows_no_empty_section(self):
        body = self._page('/regions/budva/')
        for section in ('region-hotels', 'region-places', 'region-events'):
            self.assertNotIn(f'id="{section}"', body, section)

    def test_chips_link_the_pages_with_experiences_and_count_them(self):
        body = self._page('/regions/kotor/')
        chips = body[body.index('id="region-activities"') : body.index('id="region-experiences"')]
        for path, count in (
            ('/regions/kotor/water-fun/', 1),
            ('/regions/kotor/boat-tours/', 1),
            ('/regions/kotor/hiking/', 1),
        ):
            with self.subTest(path=path):
                self.assertRegex(chips, rf'href="{path}"[^>]*>[^<]*<span[^>]*>{count}</span>')
        self.assertNotIn('/regions/kotor/closed/', chips)
        budva = self._page('/regions/budva/')
        self.assertNotIn('/regions/budva/hiking/', budva)

    def test_the_trail_starts_with_home(self):
        shown = assert_one_trail(self, self._page('/regions/kotor/'))
        self.assertEqual(shown[0], ('Home', '/'))


class FilteredListingCanonicalTests(MontenegroThemeMixin, _LandingFixtures, TestCase):
    def _canonical(self, path):
        match = _CANONICAL.search(self._page(path))
        return match.group(1) if match else ''

    def test_region_and_category_name_the_landing_page(self):
        self.assertEqual(
            self._canonical('/bookings/?region=kotor&category=water-fun'),
            'http://testserver/regions/kotor/water-fun/',
        )

    def test_a_region_alone_names_the_region_page(self):
        self.assertEqual(
            self._canonical('/bookings/?region=kotor'), 'http://testserver/regions/kotor/'
        )

    def test_a_category_alone_keeps_bookings(self):
        self.assertEqual(
            self._canonical('/bookings/?category=water-fun'), 'http://testserver/bookings/'
        )

    def test_a_query_a_date_or_a_sort_keeps_bookings(self):
        future = (timezone.localdate() + datetime.timedelta(days=10)).isoformat()
        for query in (
            'region=kotor&q=boat',
            f'region=kotor&category=water-fun&date={future}',
            'region=kotor&guests=2',
            'region=kotor&sort=rating',
        ):
            with self.subTest(query=query):
                self.assertNotIn('/regions/', self._canonical(f'/bookings/?{query}'))

    def test_the_duplicate_declares_no_graph_of_its_own(self):
        body = self._page('/bookings/?region=kotor')
        graphs = [json.loads(b) for b in _LDJSON.findall(body)]
        self.assertFalse(
            [n for g in graphs for n in g.get('@graph', []) if n.get('@type') == 'BreadcrumbList']
        )


class LandingSitemapTests(_LandingFixtures, TestCase):
    def test_it_lists_the_pairs_with_an_experience_and_no_empty_one(self):
        urls = {e['loc'] for e in contribute_sitemap_urls([])}
        for path in (
            '/regions/kotor/water-fun/',
            '/regions/kotor/boat-tours/',
            '/regions/kotor/hiking/',
            '/regions/budva/water-fun/',
            '/regions/budva/boat-tours/',
        ):
            self.assertTrue(any(u.endswith(path) for u in urls), path)
        for path in ('/regions/budva/hiking/', '/regions/kotor/closed/'):
            self.assertFalse(any(u.endswith(path) for u in urls), path)
