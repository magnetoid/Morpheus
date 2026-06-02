"""No-code JSON-LD emission toggles on Site SEO settings.

The merchant picks which schema.org blocks the storefront emits from the
SEO settings page (no edit to ``jsonld.py``). These tests pin that each
toggle actually suppresses its block while defaults keep everything on.
"""

from __future__ import annotations

from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.installed.seo.models import SiteSeoSettings
from plugins.installed.seo.services import (
    organization_jsonld,
    product_jsonld,
    website_jsonld,
)


class JsonLdToggleTests(TestCase):
    def setUp(self):
        # One settings row, created before any generator call so the
        # singleton resolver returns it.
        self.s = SiteSeoSettings.objects.create(organization_name='dot books')

    def test_all_blocks_emit_by_default(self):
        self.assertIsNotNone(organization_jsonld())
        self.assertIsNotNone(website_jsonld())

    def test_organization_toggle_off_suppresses(self):
        self.s.jsonld_organization = False
        self.s.save()
        self.assertIsNone(organization_jsonld())

    def test_website_toggle_off_suppresses(self):
        self.s.jsonld_website = False
        self.s.save()
        self.assertIsNone(website_jsonld())

    def test_product_toggle_off_returns_empty(self):
        p = Product.objects.create(
            name='Test',
            slug='test',
            sku='T1',
            price=Money(10, 'USD'),
            status='active',
        )
        self.assertEqual(product_jsonld(p).get('@type'), 'Product')
        self.s.jsonld_product = False
        self.s.save()
        self.assertEqual(product_jsonld(p), {})

    def test_reviews_toggle_off_strips_rating_and_reviews(self):
        p = Product.objects.create(
            name='R',
            slug='r',
            sku='R1',
            price=Money(10, 'USD'),
            status='active',
        )
        self.s.jsonld_reviews = False
        self.s.save()
        ld = product_jsonld(p)
        self.assertNotIn('aggregateRating', ld)
        self.assertNotIn('review', ld)
