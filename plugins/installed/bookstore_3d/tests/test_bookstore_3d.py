"""Tests for the 3D bookstore walkthrough.

The /walkthrough/ page is a PUBLIC storefront page — anyone may view it, so
the mandatory boundary test here is simply "anonymous gets 200" (there is no
staff/customer scope to enforce on it).

This plugin contributes a *SettingsPanel* but ships **no settings view of its
own** — the panel renders through admin_dashboard's already-staff-gated
generic settings view (``settings_category`` / ``plugin_settings_view``, both
``@staff_member_required``). The anon/non-staff/staff boundary trio is owned
and tested by admin_dashboard, so it is not duplicated here.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.test import Client, TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product
from plugins.registry import app_registry


class WalkthroughPublicTests(TestCase):
    def setUp(self):
        self.client = Client()
        Product.objects.create(
            name='The Glass Bead Game',
            slug='glass-bead-test',
            sku='GB-T-1',
            status='active',
            price=Money(Decimal('18.00'), 'USD'),
            product_type='simple',
            is_featured=True,
        )
        # A draft must never reach the shelves.
        Product.objects.create(
            name='Unpublished Manuscript',
            slug='unpub-test',
            sku='UN-T-1',
            status='draft',
            price=Money(Decimal('9.00'), 'USD'),
            product_type='simple',
        )

    def test_walkthrough_public_returns_200(self):
        resp = Client().get('/walkthrough/')
        self.assertEqual(resp.status_code, 200)

    def test_scene_boots_and_lists_active_book(self):
        resp = self.client.get('/walkthrough/')
        body = resp.content.decode()
        # three.js scene scaffolding is present.
        self.assertIn('importmap', body)
        self.assertIn('bookstore-books', body)
        # The active product is in the JSON island; the draft is not.
        self.assertIn('glass-bead-test', body)
        self.assertNotIn('unpub-test', body)

    def test_books_json_shape(self):
        """The data island is valid JSON with the documented keys."""
        resp = self.client.get('/walkthrough/')
        body = resp.content.decode()
        marker = '<script id="bookstore-books" type="application/json">'
        start = body.index(marker) + len(marker)
        end = body.index('</script>', start)
        books = json.loads(body[start:end])
        self.assertTrue(books)
        for key in ('title', 'slug', 'image_url', 'price', 'currency'):
            self.assertIn(key, books[0])


class WalkthroughDisabledTests(TestCase):
    """When the scene is toggled off, the page still 200s but shows the
    'closed' notice and does NOT boot three.js."""

    def test_disabled_renders_closed_notice_without_three(self):
        plugin = app_registry.get('bookstore_3d')
        self.assertIsNotNone(plugin)
        plugin.set_config('enabled', False)
        try:
            resp = Client().get('/walkthrough/')
            self.assertEqual(resp.status_code, 200)
            body = resp.content.decode()
            self.assertIn('currently closed', body)
            self.assertNotIn('importmap', body)
        finally:
            plugin.set_config('enabled', True)
