"""The croatia theme turns the travel app into a Croatian store (v0.139.0).

croatia-experience.me runs this app with the croatia theme, a copy of montenegro's
(owner, 2026-11-07). The theme names the country (`country = 'HR'`), and the app reads
its regions, structured-data address, page titles and the investor page's arrivals
from that one profile (country.py). Before it, about 80 places said Montenegro, among
them `addressCountry: 'ME'` in every listing's JSON-LD, which on a Croatian store
would be a false claim to search engines.

Croatian is served at /hr/ from locale/hr, so every string the theme and the app
mark for translation needs a Croatian entry: a missing one falls back to English
without a word.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template import engines
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation
from django.utils.translation import trans_real
from djmoney.money import Money

from plugins.installed.booking_marketplace import country
from plugins.installed.booking_marketplace.models import BookableService, Property
from plugins.installed.booking_marketplace.tests.test_serbian_catalog import _msgids
from plugins.installed.seo.services.ai_feeds import render_ai_products_feed
from themes.test_head_contract import _activate_theme

CROATIAN = override_settings(LANGUAGES=[('en', 'English'), ('hr', 'Hrvatski')])


def _jsonld(html: str) -> list:
    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S)
    return [json.loads(b) for b in blocks]


@CROATIAN
class CroatiaStoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        host = Vendor.objects.create(name='Split Kayak', slug='split-kayak', is_active=True)
        cls.svc = BookableService.objects.create(
            vendor=host,
            name='Sunset Kayak',
            slug='sunset-kayak',
            listing_kind='experience',
            region='split',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
        )
        Property.objects.create(
            vendor=host,
            name='Rovinj Rooms',
            slug='rovinj-rooms',
            region='istria',
            price_from=Decimal('90.00'),
            is_active=True,
        )

    def setUp(self):
        _activate_theme(self, 'croatia')

    def test_the_theme_names_the_country(self):
        self.assertEqual(country.current().code, 'HR')
        keys = [key for key, _label in BookableService._meta.get_field('region').choices]
        self.assertEqual(keys[:2], ['istria', 'kvarner'])
        self.assertNotIn('kotor', keys)

    def test_a_listing_takes_a_croatian_region_and_refuses_a_montenegrin_one(self):
        field = BookableService._meta.get_field('region')
        field.clean('split', self.svc)
        with self.assertRaises(ValidationError):
            field.clean('kotor', self.svc)

    def test_structured_data_says_croatia(self):
        feed = render_ai_products_feed()
        stay = next(
            e['item'] for e in feed['itemListElement'] if e['item']['name'] == 'Rovinj Rooms'
        )
        self.assertEqual(stay['address']['addressCountry'], 'HR')
        html = self.client.get('/bookings/sunset-kayak/').content.decode()
        self.assertNotIn('"addressCountry": "ME"', html)
        self.assertNotIn('Montenegro', json.dumps(_jsonld(html)))

    def test_the_listing_pages_name_croatia(self):
        html = self.client.get('/bookings/').content.decode()
        self.assertIn('Experiences in Croatia', html)
        self.assertNotIn('Montenegro', html)

    def test_the_croatian_pages_are_in_croatian(self):
        resp = self.client.get('/hr/bookings/')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('Doživljaji u Hrvatskoj', html)
        self.assertIn('Split i srednjodalmatinski otoci', html)

    def test_the_investor_page_uses_croatian_figures(self):
        html = self.client.get('/investors/').content.decode()
        body = html[html.index('<div class="inv">') :]
        # 1% of 21.8 million arrivals = 218,000 guests.
        self.assertIn('218,000', body)
        self.assertIn('Croatian National Tourist Board', body)
        self.assertNotIn('Kotor', body)
        self.assertIn('noindex', html)
        hr = self.client.get('/hr/investors/').content.decode()
        self.assertIn('218.000', hr)
        self.assertIn('Hrvatska turistička zajednica', hr)

    def test_montenegro_stays_the_default(self):
        _activate_theme(self, 'montenegro')
        self.assertEqual(country.current().code, 'ME')
        _activate_theme(self, 'dot_books')
        self.assertEqual(country.current().code, 'ME')


class CroatianCatalogTests(SimpleTestCase):
    _ROOTS = (
        Path(settings.BASE_DIR) / 'themes' / 'library' / 'croatia' / 'templates',
        Path(__file__).resolve().parents[1] / 'templates',
    )

    def test_every_translatable_string_has_a_croatian_translation(self):
        catalog = trans_real.translation('hr')._catalog
        engine = engines['django'].engine
        missing = []
        for root in self._ROOTS:
            for path in sorted(root.rglob('*.html')):
                for msgid, plural in _msgids(engine.from_string(path.read_text())):
                    if msgid and ((msgid, 0) if plural else msgid) not in catalog:
                        missing.append(f'{path.relative_to(root)}: {msgid[:80]!r}')
        self.assertEqual(missing, [], f'{len(missing)} strings without a Croatian translation')

    def test_the_country_profile_is_translated(self):
        texts = [label for _key, label in country.CROATIA.regions]
        texts += list(country.CROATIA.region_context.values())
        texts += [v for v in country.CROATIA.text.values() if not isinstance(v, tuple)]
        for text in texts:
            with translation.override('en'):
                english = str(text)
            if english in {'Zagreb', 'Croatia'}:
                continue
            with translation.override('hr'), self.subTest(text=english):
                self.assertNotEqual(str(text), english)
        with translation.override('hr'):
            self.assertEqual(
                translation.ngettext(*country.CROATIA.text['regions_count'], 3) % {'count': 3},
                'Doživljaji za rezervaciju u 3 regije Hrvatske',
            )
