"""TouristTrip and Offer on experience pages, stated only as far as the page shows them."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from django.test import TestCase, override_settings
from djmoney.money import Money

from plugins.installed.booking_marketplace import seo_jsonld
from plugins.installed.booking_marketplace.models import BookableService
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Vendor

_LDJSON = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def _nodes(html):
    return [n for blob in _LDJSON.findall(html) for n in json.loads(blob).get('@graph', [])]


def _typed(nodes, kind):
    return [n for n in nodes if n.get('@type') == kind]


class ExperienceTripJsonLdTests(MontenegroThemeMixin, TestCase):
    def setUp(self):
        self.vendor = Vendor.objects.create(name='Makers', slug='makers', is_active=True)
        self.svc = BookableService.objects.create(
            vendor=self.vendor,
            name='Kayak the bay',
            slug='kayak-the-bay',
            listing_kind='experience',
            price=Money(Decimal('50'), 'EUR'),
            is_active=True,
            short_description='Paddle at dawn.',
            itinerary=[
                {'title': 'Meet at the gate', 'detail': 'Kit and a briefing.'},
                {'title': 'Paddle under the walls', 'detail': ''},
            ],
        )

    def _page_nodes(self):
        return _nodes(self.client.get(f'/bookings/{self.svc.slug}/').content.decode())

    def test_an_experience_is_a_tourist_trip_with_its_itinerary(self):
        trips = _typed(self._page_nodes(), 'TouristTrip')
        self.assertEqual(len(trips), 1)
        steps = trips[0]['itinerary']['itemListElement']
        self.assertEqual(
            [(s['position'], s['name']) for s in steps],
            [(1, 'Meet at the gate'), (2, 'Paddle under the walls')],
        )
        self.assertEqual(steps[0]['description'], 'Kit and a briefing.')
        self.assertNotIn('description', steps[1])
        self.assertEqual(trips[0]['offers']['priceCurrency'], 'EUR')

    def test_a_product_listing_is_no_trip(self):
        BookableService.objects.filter(pk=self.svc.pk).update(listing_kind='product')
        self.assertEqual(_typed(self._page_nodes(), 'TouristTrip'), [])

    @override_settings(BOOKING_LISTING_MODE=True)
    def test_listing_mode_states_no_price(self):
        nodes = self._page_nodes()
        # Nothing for a Product to carry: no offer, no verified rating.
        self.assertEqual(_typed(nodes, 'Product'), [])
        trip = _typed(nodes, 'TouristTrip')[0]
        self.assertNotIn('offers', trip)
        webpage = next(n for n in nodes if str(n.get('@id', '')).endswith('#webpage'))
        self.assertEqual(webpage['mainEntity'], {'@id': trip['@id']})

    def test_the_offer_states_the_listings_currency(self):
        self.svc.price = Money(Decimal('50'), 'USD')
        self.svc.save()
        product = _typed(self._page_nodes(), 'Product')[0]
        self.assertEqual(product['offers']['priceCurrency'], 'USD')

    def test_malformed_steps_are_skipped(self):
        service = BookableService(
            name='X',
            slug='x',
            vendor=self.vendor,
            itinerary=['Meet', {'detail': 'no title'}, {'title': 'Paddle'}],
        )
        node = seo_jsonld._trip_node(service, url='https://x.test/bookings/x/', with_prices=False)
        steps = node['itinerary']['itemListElement']
        self.assertEqual([(s['position'], s['name']) for s in steps], [(1, 'Paddle')])
