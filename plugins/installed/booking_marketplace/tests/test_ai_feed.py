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

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import (
    BookableService,
    Booking,
    Property,
    ServiceReview,
)
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


class AiFeedRatingClaimTests(TestCase):
    """A rating in the feed is a claim to every AI crawler, so only reviews a
    guest wrote through `create_review`'s booking gate may back one.

    The feed read the denormalised `rating`/`review_count` columns and
    published 40,733 reviews while the live database held 559 — every one
    written by `seed_reviews`, and 100 of the ratings computed from a hash of
    the hotel's slug. Both directions are asserted: unverified → absent,
    verified → present and counted alone.
    """

    @classmethod
    def setUpTestData(cls):
        vendor = Vendor.objects.create(name='Tara Sport', slug='tara-sport', is_active=True)
        cls.svc = BookableService.objects.create(
            vendor=vendor,
            name='Tara Canyon Rafting',
            slug='tara-canyon-rafting',
            price=Decimal('55.00'),
            rating=Decimal('4.8'),
            review_count=12,
            is_active=True,
        )
        cls.prop = Property.objects.create(
            vendor=vendor,
            name='Aman Sveti Stefan',
            slug='aman-sveti-stefan',
            location='Budva',
            star_rating=5,
            price_from=Decimal('900.00'),
            rating=Decimal('4.5'),
            review_count=301,
            is_active=True,
        )

    def _item(self, name):
        feed = render_ai_products_feed()
        return next(e['item'] for e in feed['itemListElement'] if e['item']['name'] == name)

    def _guest_review(self, rating, email):
        """A review through the real gate: a booking first, then create_review."""
        U = get_user_model()
        guest = U.objects.create(**{U.USERNAME_FIELD: email})
        Booking.objects.create(
            service=self.svc,
            customer=guest,
            customer_name='Guest',
            customer_email=email,
            booking_date=timezone.localdate() + datetime.timedelta(days=2),
            guests=1,
            status='confirmed',
        )
        S.create_review(self.svc, user=guest, rating=rating, body='A real trip.')

    def test_denormalised_columns_alone_publish_no_rating(self):
        self.assertNotIn('aggregateRating', self._item('Tara Canyon Rafting'))

    def test_seeded_reviews_publish_no_rating(self):
        ServiceReview.objects.bulk_create(
            ServiceReview(service=self.svc, author_name='Sarah M.', rating=5, body='Seeded.')
            for _ in range(3)
        )
        self.assertNotIn('aggregateRating', self._item('Tara Canyon Rafting'))

    def test_verified_reviews_are_published_and_counted_alone(self):
        ServiceReview.objects.create(
            service=self.svc, author_name='Sarah M.', rating=1, body='Seeded.'
        )
        self._guest_review(5, 'a@x.io')
        self._guest_review(4, 'b@x.io')
        self.assertEqual(
            self._item('Tara Canyon Rafting')['aggregateRating'],
            {'@type': 'AggregateRating', 'ratingValue': '4.5', 'reviewCount': 2},
        )

    def test_a_stay_never_claims_a_guest_rating(self):
        """Property has no review model at all; its columns are editorial."""
        hotel = self._item('Aman Sveti Stefan')
        self.assertNotIn('aggregateRating', hotel)
        # The hotel's class is a fact about the hotel, not a review — it stays.
        self.assertEqual(hotel['starRating']['ratingValue'], 5)

    def test_rating_costs_no_query_per_experience(self):
        """The feed annotates once. verified_rating's per-row fallback is
        correct but would cost ~140 queries per crawler hit on the live store."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def count_queries():
            with CaptureQueriesContext(connection) as ctx:
                render_ai_products_feed()
            return len(ctx.captured_queries)

        count_queries()  # warm any settings caches out of the measurement
        before = count_queries()
        for i in range(5):
            BookableService.objects.create(
                vendor=self.svc.vendor,
                name=f'Extra {i}',
                slug=f'extra-{i}',
                price=Decimal('10.00'),
                is_active=True,
            )
        self.assertEqual(count_queries(), before)
