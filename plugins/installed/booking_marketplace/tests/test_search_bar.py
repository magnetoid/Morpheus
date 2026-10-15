"""One search bar for the travel store (booking_marketplace/_search.html).

The home hero and /bookings/ carried two copies of one form and /shop/ had none, the
labels were tied to no field, Where listed regions with nothing to book, and the date
field read "dd. mm. yyyy.".
"""

from __future__ import annotations

import datetime
import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import search_page
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor

SCRIPT = (
    Path(settings.BASE_DIR)
    / 'themes'
    / 'library'
    / 'montenegro'
    / 'static'
    / 'montenegro'
    / 'search.js'
)
_BAR = re.compile(r'<div class="mx-sb mx-sb--(?P<variant>\w+)"[^>]*data-mx-search=.*?</form>', re.S)


def bars(body):
    return [(match.group('variant'), match.group(0)) for match in _BAR.finditer(body)]


class _Controls(HTMLParser):
    """The bar's fields and the ids its labels point at."""

    def __init__(self):
        super().__init__()
        self.fields, self.labelled = [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'label' and attrs.get('for'):
            self.labelled.add(attrs['for'])
        if tag in ('input', 'select') and attrs.get('type') not in ('hidden', 'submit', 'button'):
            self.fields.append(attrs.get('id'))


class BarFixture(MontenegroThemeMixin):
    def setUp(self):
        super().setUp()
        vendor = Vendor.objects.create(name='Host', slug='host', is_active=True)
        water = Category.objects.create(name='Water Sports', slug='water-sports')
        for slug, region in (('kotor-a', 'kotor'), ('kotor-b', 'kotor'), ('budva-a', 'budva')):
            BookableService.objects.create(
                vendor=vendor,
                name=slug,
                slug=slug,
                region=region,
                category=water,
                price=Money(50, 'EUR'),
            )
        BookableService.objects.create(
            vendor=vendor,
            name='Honey',
            slug='honey',
            region='skadar',
            listing_kind='product',
            price=Money(9, 'EUR'),
        )
        self.day = timezone.localdate() + datetime.timedelta(days=4)

    def _body(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.content.decode()

    def _bar(self, path):
        (found,) = bars(self._body(path))
        return found[1]


@override_settings(BOOKING_LISTING_MODE=False)
class SearchBarTests(BarFixture, TestCase):
    def test_one_bar_on_the_listings_and_the_shop(self):
        self.assertEqual([variant for variant, _ in bars(self._body('/bookings/'))], ['bar'])
        self.assertEqual([variant for variant, _ in bars(self._body('/shop/'))], ['shop'])

    def test_the_old_partial_is_gone(self):
        with self.assertRaises(TemplateDoesNotExist):
            get_template('booking_marketplace/_search_bar.html')

    def test_every_field_has_a_label(self):
        for path in ('/bookings/', '/shop/'):
            controls = _Controls()
            controls.feed(self._bar(path))
            with self.subTest(path=path):
                self.assertTrue(controls.fields)
                self.assertTrue(all(controls.fields), 'a field without an id')
                self.assertLessEqual(set(controls.fields), controls.labelled)

    def test_where_lists_regions_with_live_experiences(self):
        bar = self._bar('/bookings/')
        where = re.search(r'<select[^>]*name="region".*?</select>', bar, re.S).group(0)
        self.assertEqual(re.findall(r'<option value="(\w*)"', where), ['', 'kotor', 'budva'])
        self.assertIn('Kotor Bay (2)', where)
        self.assertIn('Budva Riviera (1)', where)

    def test_categories_by_slug_and_selected_from_a_name(self):
        self.assertRegex(
            self._bar('/bookings/?category=Water+Sports'), r'<option value="water-sports" selected>'
        )

    def test_the_bar_shows_the_search(self):
        bar = self._bar(f'/bookings/?q=kayak&region=kotor&date={self.day.isoformat()}')
        self.assertIn('value="kayak"', bar)
        self.assertRegex(bar, r'<option value="kotor" selected>')
        self.assertIn(f'value="{self.day.isoformat()}"', bar)
        self.assertIn(search_page.date_label(self.day), bar)
        self.assertIn(f'min="{timezone.localdate().isoformat()}"', bar)

    def test_the_shop_bar_searches_goods(self):
        bar = self._bar('/shop/')
        self.assertIn('action="/shop/"', bar)
        self.assertNotIn('name="region"', bar)
        self.assertNotIn('data-suggest-url', bar)

    def test_the_listings_bar_asks_for_suggestions(self):
        bar = self._bar('/bookings/')
        self.assertIn('data-suggest-url="/bookings/suggest/"', bar)
        self.assertIn('role="combobox"', bar)
        self.assertIn('aria-controls="sb-list-bar"', bar)

    def test_the_script_is_deferred(self):
        self.assertRegex(
            self._body('/bookings/'),
            r'<script src="[^"]*montenegro/search(\.[0-9a-f]+)?\.js" defer>',
        )

    def test_the_script_never_writes_html(self):
        source = SCRIPT.read_text()
        for sink in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write'):
            with self.subTest(sink=sink):
                self.assertNotIn(sink, source)
        self.assertIn('textContent', source)


@serbian_enabled
@override_settings(BOOKING_LISTING_MODE=False)
class SerbianSearchBarTests(BarFixture, TestCase):
    def test_the_bar_follows_the_language(self):
        bar = self._bar(f'/sr/bookings/?date={self.day.isoformat()}')
        self.assertIn('data-suggest-url="/sr/bookings/suggest/"', bar)
        self.assertIn('data-date-locale="sr-Latn-ME"', bar)
        self.assertIn('action="/sr/bookings/"', bar)
        self.assertIsNone(re.search('[Ѐ-ӿ]', bar), 'Cyrillic in the Serbian search bar')
