"""Product JSON-LD on experience pages — rating only when reviews exist."""

import json
import re

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.booking_marketplace.models import BookableService, ServiceReview
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


class ExperienceJsonLdTests(TestCase):
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

    def test_rating_block_only_with_reviews(self):
        ServiceReview.objects.all().delete()
        BookableService.objects.filter(pk=self.svc.pk).update(review_count=0, rating=0)
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        html = resp.content.decode()
        self.assertNotIn('AggregateRating', html)
        # sanity: the Product node itself still renders without a rating.
        self.assertIn('Product', _find_types(html))

    def test_script_tag_not_breakable_by_content(self):
        resp = self.client.get(f'/bookings/{self.svc.slug}/')
        self.assertNotContains(resp, '<script>alert')
