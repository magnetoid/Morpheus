"""The preview reader is an indexable page with a head of its own.

It used to add ``<meta name="robots" content="noindex, follow">`` beside the
head document's own robots tag, so every reader page carried two robots tags
and stayed out of the index; and with no title of its own it would have
shared the product page's title once indexed.
"""

from __future__ import annotations

import re
from decimal import Decimal

from django.test import TestCase
from djmoney.money import Money


class ReaderHeadTests(TestCase):
    def setUp(self):
        from plugins.installed.catalog.models import Product

        Product.objects.create(
            name='The Huguenots',
            slug='the-huguenots',
            sku='HUG-1',
            status='active',
            price=Money(Decimal('9.00'), 'USD'),
            digital_file='digital/the-huguenots.pdf',
        )

    def test_one_robots_tag_and_it_allows_indexing(self):
        resp = self.client.get('/p/the-huguenots/flipbook/')
        self.assertEqual(resp.status_code, 200)
        robots = re.findall(r'<meta name="robots" content="([^"]*)"', resp.content.decode())
        self.assertEqual(len(robots), 1, robots)
        self.assertNotIn('noindex', robots[0])

    def test_title_is_not_the_product_pages_title(self):
        html = self.client.get('/p/the-huguenots/flipbook/').content.decode()
        title = re.search(r'<title>([^<]*)</title>', html).group(1)
        self.assertIn('The Huguenots', title)
        self.assertIn('preview', title.lower())
