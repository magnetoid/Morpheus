"""The investor page shows public market figures and the live catalogue, nothing internal (v0.138.0).

The owner asked for a page to show investors (2026-11-06) with no figure from the
store's own operations: no bookings, enquiries or revenue, and no word on which steps
of the booking flow are switched on. The catalogue counts are what the public site
lists, counted live, and the scenarios are public arrivals × the median listed price
× the service fee.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, Property
from plugins.installed.booking_marketplace.tests._i18n import serbian_enabled
from themes.test_head_contract import _activate_theme


def _page_body(html: str) -> str:
    """The page's own content, without the shared header and footer."""
    return html[
        html.index('<div class="inv">') : html.index(
            '<script nonce=', html.index('<div class="inv">')
        )
    ]


@serbian_enabled
class InvestorPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from plugins.installed.catalog.models import Vendor

        tara = Vendor.objects.create(name='Tara Sport', slug='tara-sport', is_active=True)
        kotor = Vendor.objects.create(name='Kotor Sail', slug='kotor-sail', is_active=True)
        gone = Vendor.objects.create(name='Gone', slug='gone', is_active=False)
        for vendor, slug, price, region in (
            (tara, 'rafting', 40, 'durmitor'),
            (tara, 'canyon', 60, 'durmitor'),
            (kotor, 'sailing', 95, 'kotor'),
            (gone, 'hidden', 500, 'kotor'),
        ):
            BookableService.objects.create(
                vendor=vendor,
                name=slug.title(),
                slug=slug,
                listing_kind='experience',
                region=region,
                price=Money(Decimal(price), 'EUR'),
                is_active=True,
            )
        Property.objects.create(
            vendor=kotor, name='Old Town Rooms', slug='old-town-rooms', is_active=True
        )
        # A guesthouse that offers no experience is still a host on the site.
        inn = Vendor.objects.create(name='Bay Inn', slug='bay-inn', is_active=True)
        Property.objects.create(vendor=inn, name='Bay Inn', slug='bay-inn', is_active=True)

    def setUp(self):
        _activate_theme(self, 'montenegro')

    def test_the_page_counts_what_the_site_lists(self):
        resp = self.client.get('/investors/')
        self.assertEqual(resp.status_code, 200)
        ctx = resp.context['catalogue']
        # A listing from a host who is switched off is not on the site.
        self.assertEqual(ctx['experiences'], 3)
        self.assertEqual(ctx['hosts'], 3)
        self.assertEqual(ctx['stays'], 2)
        self.assertEqual(ctx['regions'], 2)
        self.assertEqual(ctx['median_price'], Decimal('60'))

    def test_scenarios_are_arrivals_times_median_price_times_fee(self):
        body = _page_body(self.client.get('/investors/').content.decode())
        # 1% of 2,728,564 arrivals = 27,286 guests; × €60 = €1.64M; × 12% = €196.5K.
        self.assertIn('27,286', body)
        self.assertIn('€1.6M', body)
        self.assertIn('€196.5K', body)

    def test_nothing_from_the_store_operations(self):
        body = _page_body(self.client.get('/investors/').content.decode()).lower()
        for pattern in (
            r'enquir',
            r'booking request',
            r'switched on',
            r'\btraction\b',
            r'revenue to date',
            r'€0\b',
        ):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, body))

    def test_it_is_shared_by_link_and_kept_out_of_the_index(self):
        html = self.client.get('/investors/').content.decode()
        self.assertIn('noindex', html)

    def test_the_serbian_page_is_in_serbian(self):
        resp = self.client.get('/sr/investors/')
        self.assertEqual(resp.status_code, 200)
        body = _page_body(resp.content.decode())
        self.assertIn('Za investitore', body)
        self.assertIn('27.286', body)
        self.assertNotIn('For investors', body)

    def test_a_theme_without_the_page_answers_404(self):
        _activate_theme(self, 'dot_books')
        self.assertEqual(self.client.get('/investors/').status_code, 404)
