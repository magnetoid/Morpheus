"""Journal feed autodiscovery is a seo *contribution* — present while the plugin
is active, gone (with the page still answering) when it is disabled. It used
to be two hard `{% url 'seo:…' %}` lines in the theme's <head>, which 500'd
every storefront page once seo was disabled and its URLs unregistered."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from plugins.registry import app_registry


class FeedLinksBlockTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_head_carries_feed_links_while_seo_is_active(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        head = r.content.decode().split('</head>', 1)[0]
        self.assertIn('href="/journal/feed.xml"', head)
        self.assertIn('href="/journal/atom.xml"', head)

    def test_disabling_seo_drops_the_links_and_keeps_the_page_up(self):
        app_registry.deactivate('seo')
        try:
            cache.clear()
            r = self.client.get('/')
            self.assertEqual(r.status_code, 200)
            self.assertNotIn('journal/feed.xml', r.content.decode())
        finally:
            app_registry.activate('seo')
