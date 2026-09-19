"""/ai/products.json must carry this store's real inventory.

The feed is built from catalog ``Product`` rows. This store sells
``BookableService`` and ``Property``, so the feed shipped reporting
``numberOfItems: 0`` — every AI shopping crawler was told the shop was
empty while 142 experiences and 100 stays were live.

Locks the AI_FEED_ITEMS contribution, and the pagination maths over the
combined catalog+contributed sequence (a naive fix double-counts or drops
the contributed tail).
"""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from plugins.installed.booking_marketplace.models import BookableService, Property
from plugins.installed.catalog.models import Vendor
from plugins.installed.seo.services.ai_feeds import render_ai_products_feed


class AiFeedContributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vendor = Vendor.objects.create(name='Tara Sport', slug='tara-sport', is_active=True)
        cls.svc = BookableService.objects.create(
            vendor=cls.vendor,
            name='Tara Canyon Rafting',
            slug='tara-canyon-rafting',
            short_description='Half-day rafting through the deepest canyon in Europe.',
            price=Decimal('55.00'),
            rating=Decimal('4.8'),
            review_count=12,
            is_active=True,
        )
        cls.prop = Property.objects.create(
            vendor=cls.vendor,
            name='Boutique Hotel Astoria',
            slug='boutique-hotel-astoria',
            location='Kotor',
            star_rating=4,
            price_from=Decimal('98.00'),
            is_active=True,
        )

    def _items(self, **kw):
        feed = render_ai_products_feed(**kw)
        return feed, [e['item'] for e in feed['itemListElement']]

    def test_experiences_and_stays_appear_in_the_feed(self):
        feed, items = self._items()
        self.assertEqual(feed['numberOfItems'], 2)
        names = {i['name'] for i in items}
        self.assertEqual(names, {'Tara Canyon Rafting', 'Boutique Hotel Astoria'})

    def test_experience_carries_a_priced_offer(self):
        _, items = self._items()
        svc = next(i for i in items if i['name'] == 'Tara Canyon Rafting')
        self.assertEqual(svc['@type'], 'Product')
        self.assertEqual(svc['offers']['price'], '55.00')
        self.assertEqual(svc['offers']['priceCurrency'], 'EUR')
        self.assertTrue(svc['url'].endswith('/bookings/tara-canyon-rafting/'))
        self.assertEqual(svc['aggregateRating']['reviewCount'], 12)

    def test_stay_is_a_hotel_with_a_price_floor_not_a_fixed_price(self):
        """`price_from` is a nightly floor — quoting it as a fixed `price`
        would misrepresent what the traveller actually pays."""
        _, items = self._items()
        prop = next(i for i in items if i['name'] == 'Boutique Hotel Astoria')
        self.assertEqual(prop['@type'], 'Hotel')
        self.assertNotIn('price', prop.get('makesOffer', {}))
        self.assertEqual(prop['makesOffer']['priceSpecification']['minPrice'], '98.00')
        self.assertEqual(prop['address']['addressCountry'], 'ME')

    def test_inactive_rows_are_excluded(self):
        BookableService.objects.filter(pk=self.svc.pk).update(is_active=False)
        feed, _ = self._items()
        self.assertEqual(feed['numberOfItems'], 1)

    def test_rows_of_an_inactive_vendor_are_excluded(self):
        Vendor.objects.filter(pk=self.vendor.pk).update(is_active=False)
        feed, _ = self._items()
        self.assertEqual(feed['numberOfItems'], 0)

    def test_pagination_walks_the_contributed_tail_without_repeating(self):
        first, first_items = self._items(limit=1, offset=0)
        second, second_items = self._items(limit=1, offset=1)
        self.assertEqual(first['numberOfItems'], 2)
        self.assertEqual(len(first_items), 1)
        self.assertEqual(len(second_items), 1)
        self.assertNotEqual(first_items[0]['name'], second_items[0]['name'])
        self.assertIn('nextPage', first)  # more to fetch
        self.assertNotIn('nextPage', second)  # tail reached

    def test_positions_are_sequential_across_the_window(self):
        feed = render_ai_products_feed(limit=10, offset=0)
        self.assertEqual([e['position'] for e in feed['itemListElement']], [1, 2])
