"""/ai/products.json is served from a server-side cache.

Rendering the feed walks the whole catalogue: 12 seconds and 1.25 MB per
request on the bookshop, redone for every crawler hit. The response already
promised ``max-age=900``; the server now honours the same window itself.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase


class AiFeedCacheTests(TestCase):
    def setUp(self):
        from plugins.installed.seo.services import site_settings

        cache.clear()
        settings = site_settings()
        settings.ai_shopping_feed_enabled = True
        settings.save()

    def test_a_repeat_request_does_not_rebuild_the_feed(self):
        with patch(
            'plugins.installed.seo.views.render_ai_products_feed', return_value={'products': []}
        ) as build:
            first = self.client.get('/ai/products.json')
            second = self.client.get('/ai/products.json')
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(build.call_count, 1)

    def test_a_different_page_of_the_feed_is_built_separately(self):
        with patch(
            'plugins.installed.seo.views.render_ai_products_feed', return_value={'products': []}
        ) as build:
            self.client.get('/ai/products.json')
            self.client.get('/ai/products.json?limit=5&offset=5')
        self.assertEqual(build.call_count, 2)
