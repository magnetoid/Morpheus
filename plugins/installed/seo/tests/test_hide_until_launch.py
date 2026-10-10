"""A store can stay out of search engines until it launches.

``hide_until_launch`` (Settings → SEO) keeps a store that is being set up out
of every index without hiding it from people: each page says
``noindex, nofollow``, the sitemaps list nothing, robots.txt names no sitemap
(crawling stays allowed, so the noindex is seen and an already-indexed URL
drops out), the AI discovery files answer 404, and nothing pings IndexNow.
Off (the default), nothing changes. The setting is read fresh, because the
merchant flips it in one worker process and every other one must follow.
"""

from __future__ import annotations

import re
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from djmoney.money import Money

from plugins.installed.catalog.models import Product

_KEY = 'hide_until_launch'


def _robots(html: str) -> list[str]:
    return re.findall(r'<meta name="robots" content="([^"]*)"', html)


class HideUntilLaunchTests(TestCase):
    def setUp(self):
        from plugins.installed.seo.models import SiteSeoSettings
        from plugins.registry import app_registry

        cache.clear()
        Product.objects.create(
            name='Water kit',
            slug='water-kit',
            sku='WK-1',
            status='active',
            price=Money(Decimal('20.00'), 'USD'),
        )
        settings_row = SiteSeoSettings.load() if hasattr(SiteSeoSettings, 'load') else None
        if settings_row is not None and hasattr(settings_row, 'llms_txt_enabled'):
            settings_row.llms_txt_enabled = True
            settings_row.save()
        self.seo = app_registry.get('seo')
        self.addCleanup(self.seo.invalidate_config_cache)
        self.addCleanup(cache.clear)

    def _hide(self):
        self.seo.set_config(_KEY, True)
        cache.clear()

    def test_off_pages_are_indexable_and_the_sitemap_lists_them(self):
        self.assertNotIn('noindex', _robots(self.client.get('/').content.decode())[0])
        self.assertIn('water-kit', self.client.get('/sitemap.xml').content.decode())
        self.assertIn('Sitemap:', self.client.get('/robots.txt').content.decode())

    def test_on_every_page_is_noindex_nofollow(self):
        self._hide()
        for path in ('/', '/products/water-kit/'):
            with self.subTest(path=path):
                robots = _robots(self.client.get(path).content.decode())
                self.assertEqual(robots, ['noindex, nofollow'])

    def test_on_the_sitemaps_list_nothing(self):
        self._hide()
        sitemap = self.client.get('/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn('<urlset', sitemap.content.decode())
        self.assertNotIn('<url>', sitemap.content.decode())
        index = self.client.get('/sitemap-index.xml').content.decode()
        self.assertIn('<sitemapindex', index)
        self.assertNotIn('<sitemap>', index)

    def test_on_robots_names_no_sitemap_but_still_allows_crawling(self):
        self._hide()
        robots = self.client.get('/robots.txt').content.decode()
        self.assertNotIn('Sitemap:', robots)
        self.assertNotIn('Disallow: /\n', robots.replace('Disallow: /admin', ''))

    def test_on_the_ai_discovery_files_are_gone(self):
        self._hide()
        for path in ('/llms.txt', '/llms-full.txt', '/agents.md', '/ai/products.json'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_on_nothing_pings_indexnow(self):
        from plugins.installed.seo.services.indexnow import ping_indexnow

        self._hide()
        with mock.patch('urllib.request.urlopen') as urlopen:
            ping_indexnow(['https://example.com/products/water-kit/'])
        urlopen.assert_not_called()

    def test_a_switch_flipped_by_another_process_is_seen(self):
        from plugins.models import PluginConfig

        self.seo.get_config()  # this process has cached the switch as off
        row, _ = PluginConfig.objects.get_or_create(plugin_name='seo')
        row.config = {**(row.config or {}), _KEY: True}
        row.save()
        cache.clear()
        self.assertEqual(_robots(self.client.get('/').content.decode()), ['noindex, nofollow'])
