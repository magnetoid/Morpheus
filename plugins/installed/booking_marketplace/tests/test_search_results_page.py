"""The results page says what was searched (booking_marketplace/list.html).

The heading never reflected the search, the filters in force were invisible, the sort
form dropped the date, and zero results offered only "Clear filters".
"""

from __future__ import annotations

import datetime
import re

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor


class PageFixture(MontenegroThemeMixin):
    def setUp(self):
        super().setUp()
        self.vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        BookableService.objects.create(
            vendor=self.vendor,
            name='Sunset Kayak Tour',
            slug='kotor-kayak',
            location='Kotor',
            region='kotor',
            category=water,
            price=Money(50, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak and Snorkel Tour',
            slug='budva-kayak',
            location='Budva',
            region='budva',
            category=water,
            price=Money(50, 'EUR'),
        )
        BookableService.objects.create(
            vendor=self.vendor,
            name='Wild Mountain Honey',
            slug='wild-honey',
            listing_kind='product',
            price=Money(9, 'EUR'),
        )
        self.day = timezone.localdate() + datetime.timedelta(days=6)

    def _body(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def _heading(self, body):
        return re.search(r'<h1 id="results-heading"[^>]*>(.*?)</h1>', body, re.S).group(1).strip()


@override_settings(BOOKING_LISTING_MODE=False)
class ResultsPageTests(PageFixture, TestCase):
    def test_the_heading_says_what_was_searched(self):
        self.assertEqual(
            self._heading(self._body('/bookings/?q=kayak&region=kotor')), '“kayak” in Kotor Bay'
        )
        self.assertEqual(
            self._heading(self._body('/bookings/?category=water-sports')),
            'Water Sports experiences in Montenegro',
        )
        self.assertEqual(self._heading(self._body('/bookings/')), 'Experiences in Montenegro')
        self.assertEqual(
            self._heading(self._body(f'/bookings/?q=kayak&date={self.day.isoformat()}')),
            f'“kayak” in Montenegro on {search_page.date_label(self.day)}',
        )

    def test_the_intro_steps_aside_for_a_search(self):
        self.assertIn('id="results-intro"', self._body('/bookings/'))
        self.assertNotIn('id="results-intro"', self._body('/bookings/?q=kayak'))

    def test_a_chip_per_filter_each_removing_itself(self):
        body = self._body(
            f'/bookings/?q=kayak&region=kotor&category=water-sports&date={self.day.isoformat()}'
        )
        chips = {
            param: href
            for href, param in re.findall(
                r'<a href="([^"]*)" class="mx-chip" data-chip="(\w+)"', body
            )
        }
        self.assertEqual(set(chips), {'q', 'region', 'date', 'category'})
        for param, href in chips.items():
            with self.subTest(param=param):
                self.assertNotIn(f'{param}=', href)
        self.assertRegex(body, r'<a href="/bookings/" class="mx-chips__clear" data-chip-clear>')

    def test_the_sort_form_keeps_every_filter(self):
        body = self._body(
            f'/bookings/?q=kayak&region=kotor&category=Water+Sports&date={self.day.isoformat()}'
        )
        form = re.search(r'<form id="sort-form".*?</form>', body, re.S).group(0)
        for name, value in (
            ('q', 'kayak'),
            ('region', 'kotor'),
            ('category', 'water-sports'),
            ('date', self.day.isoformat()),
        ):
            with self.subTest(name=name):
                self.assertIn(f'<input type="hidden" name="{name}" value="{value}">', form)
        self.assertRegex(form, r'<option value="best" selected>')
        plain = re.search(r'<form id="sort-form".*?</form>', self._body('/bookings/'), re.S).group(
            0
        )
        self.assertNotIn('value="best"', plain)

    def test_paging_keeps_the_date(self):
        for i in range(48):
            BookableService.objects.create(
                vendor=self.vendor, name=f'Extra {i}', slug=f'extra-{i}', price=Money(10, 'EUR')
            )
        body = self._body(f'/bookings/?date={self.day.isoformat()}')
        following = re.search(r'<a href="([^"]*)" rel="next"', body).group(1)
        self.assertIn(f'date={self.day.isoformat()}', following)
        self.assertIn('page=2', following)

    def test_nothing_found_names_the_search_and_offers_a_way_on(self):
        body = self._body(f'/bookings/?q=zzzz&date={self.day.isoformat()}')
        self.assertIn('id="no-results"', body)
        self.assertIn(f'No experiences match “zzzz” on {search_page.date_label(self.day)}', body)
        self.assertIn('data-popular-category="water-sports"', body)
        self.assertIn('href="/bookings/?category=water-sports"', body)
        self.assertNotIn('id="results-count"', body)

    def test_close_matches_are_labelled(self):
        body = self._body('/bookings/?q=kayak+ulcinj')
        self.assertIn('id="close-matches"', body)
        self.assertIn('No experiences match “kayak ulcinj”', body)
        self.assertRegex(body, r'<h3[^>]*><a href="/bookings/kotor-kayak/" class="card-link">')
        self.assertNotIn('id="results-count"', body)

    def test_a_past_date_says_so(self):
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        self.assertIn('id="date-note"', self._body(f'/bookings/?date={yesterday}'))

    def test_the_query_is_escaped(self):
        body = self._body('/bookings/?q=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', body)

    def test_the_shop_says_what_it_found(self):
        body = self._body('/shop/?q=zzzz')
        self.assertIn('No products match “zzzz”', body)
        self.assertIn('data-chip="q"', body)
        self.assertIn('id="no-results"', body)
        self.assertEqual(self._heading(self._body('/shop/?q=honey')), 'Shop Montenegro')


class ChipLinkTests(SimpleTestCase):
    def test_a_chip_drops_its_parameter_and_the_page(self):
        request = RequestFactory().get(
            '/bookings/', {'q': 'kayak', 'region': 'kotor', 'page': '2', 'sort': 'rating'}
        )
        params = search_page.SearchParams(q='kayak', region='kotor', region_label='Kotor Bay')
        chips = {chip['param']: chip['href'] for chip in search_page.chips(request, params)}
        self.assertEqual(chips['q'], '/bookings/?region=kotor&sort=rating')
        self.assertEqual(chips['region'], '/bookings/?q=kayak&sort=rating')


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianResultsPageTests(PageFixture, TestCase):
    def test_serbian_heading(self):
        self.assertEqual(self._heading(self._body('/sr/bookings/?q=kajak')), '„kajak“ u Crnoj Gori')
