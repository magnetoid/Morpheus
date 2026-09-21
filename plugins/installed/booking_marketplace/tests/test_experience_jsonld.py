"""Product JSON-LD on experience pages — rating only when verified guest
reviews back it."""

import datetime
import json
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from djmoney.money import Money

from plugins.installed.booking_marketplace import services as S
from plugins.installed.booking_marketplace.models import (
    BookableService,
    Booking,
    ServiceReview,
)
from plugins.installed.booking_marketplace.tests._theme import MontenegroThemeMixin
from plugins.installed.catalog.models import Category, Vendor

_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


def _graphs(html):
    """Parse every ld+json script body in the page into its @graph list."""
    graphs = []
    for blob in _LDJSON_RE.findall(html):
        data = json.loads(blob)
        graphs.append(data.get('@graph', []))
    return graphs


def _find_types(html):
    types = set()
    for graph in _graphs(html):
        for node in graph:
            if '@type' in node:
                types.add(node['@type'])
    return types


class ExperienceJsonLdTests(MontenegroThemeMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        v = Vendor.objects.create(name='Host', slug='host', is_active=True)
        c = Category.objects.create(name='Adventure', slug='adventure')
        cls.svc = BookableService.objects.create(
            vendor=v,
            category=c,
            name='Raft "the" Tara <script>',
            slug='raft-tara',
            short_description='desc',
            description='body',
            price=Money(80, 'EUR'),
            listing_kind='experience',
            is_active=True,
            rating=4.8,
            review_count=3,
        )
        ServiceReview.objects.create(service=cls.svc, author_name='Ana', rating=5, body='Great')

    def test_product_graph_present_and_parses(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        html = resp.content.decode()
        types = _find_types(html)
        self.assertIn('Product', types)
        self.assertIn('BreadcrumbList', types)

    def _product(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        for graph in _graphs(resp.content.decode()):
            for node in graph:
                if node.get('@id', '').endswith(f'/bookings/{self.svc.slug}/#product'):
                    return node
        self.fail('no Product node for this experience')

    def test_unverified_ratings_publish_nothing(self):
        """The fixture is the live condition: the columns say 4.8 from 3, one
        seeded review exists, and no guest ever booked. The page shipped
        "4.8 from 3 reviews" while showing one."""
        product = self._product()
        self.assertNotIn('aggregateRating', product)
        self.assertNotIn('review', product)

    def test_verified_reviews_publish_rating_and_nodes_from_the_same_set(self):
        U = get_user_model()
        guest = U.objects.create(**{U.USERNAME_FIELD: 'guest@x.io'})
        Booking.objects.create(
            service=self.svc,
            customer=guest,
            customer_name='Guest',
            customer_email='guest@x.io',
            booking_date=timezone.localdate() + datetime.timedelta(days=2),
            guests=1,
            status='confirmed',
        )
        S.create_review(self.svc, user=guest, rating=4, body='A real trip.')
        product = self._product()
        # create_review re-synced the columns over BOTH rows (2 reviews, 4.5);
        # the markup must still count the verified one alone.
        self.assertEqual(
            product['aggregateRating'],
            {'@type': 'AggregateRating', 'ratingValue': '4.0', 'reviewCount': 1},
        )
        self.assertEqual([r['reviewBody'] for r in product['review']], ['A real trip.'])

    def test_script_tag_not_breakable_by_content(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertNotContains(resp, '<script>alert')
