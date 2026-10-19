"""/ai/products.json is served from a server-side cache.

Rendering the feed walks the whole catalogue: 12 seconds and 1.25 MB per
request on the bookshop, redone for every crawler hit. The response already
promised ``max-age=900``; the server now honours the same window itself.

And the first request after the cache lapsed still paid the whole build (8.7 s on
Supernatural, SEO audit 2026-10-18), so a beat task rebuilds the first page
before it lapses.
"""

from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

_BUILD = 'plugins.installed.seo.services.ai_feeds.render_ai_products_feed'


class AiFeedCacheTests(TestCase):
    def setUp(self):
        from plugins.installed.seo.services import site_settings

        cache.clear()
        settings = site_settings()
        settings.ai_shopping_feed_enabled = True
        settings.save()

    def test_a_repeat_request_does_not_rebuild_the_feed(self):
        with patch(_BUILD, return_value={'products': []}) as build:
            first = self.client.get('/ai/products.json')
            second = self.client.get('/ai/products.json')
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(build.call_count, 1)

    def test_a_different_page_of_the_feed_is_built_separately(self):
        with patch(_BUILD, return_value={'products': []}) as build:
            self.client.get('/ai/products.json')
            self.client.get('/ai/products.json?limit=5&offset=5')
        self.assertEqual(build.call_count, 2)

    def test_the_warm_task_builds_the_feed_before_any_crawler_asks(self):
        from plugins.installed.seo.tasks import warm_ai_feed_task

        with patch(_BUILD, return_value={'products': []}) as build:
            warm_ai_feed_task()
            response = self.client.get('/ai/products.json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build.call_count, 1)

    def test_the_warm_task_skips_a_store_without_the_feed(self):
        from plugins.installed.seo.services import site_settings
        from plugins.installed.seo.tasks import warm_ai_feed_task

        settings = site_settings()
        settings.ai_shopping_feed_enabled = False
        settings.save()
        with patch(_BUILD, return_value={'products': []}) as build:
            warm_ai_feed_task()
        self.assertEqual(build.call_count, 0)
