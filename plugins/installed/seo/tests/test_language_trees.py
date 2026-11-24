"""A private page is private in every language's tree.

montenegro-experience.me served `/cart/` and `/checkout/` as `noindex, nofollow`
and blocked them in robots.txt, while `/sr/cart/` and `/sr/checkout/` were
`index, follow` with a canonical and hreflang, and crawlable: the private-path
check matched the path with its language prefix, and owners disallow the
address they route.
"""

from __future__ import annotations

import re

from django.core.cache import cache
from django.test import TestCase, override_settings

from plugins.installed.seo.pages.resolve import _is_private
from plugins.installed.seo.services.crawler_files import render_robots_txt

_LANGUAGES = [('en', 'English'), ('sr', 'Srpski')]


@override_settings(LANGUAGES=_LANGUAGES, LANGUAGE_CODE='en')
class PrivateInEveryLanguageTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_the_prefixed_cart_and_checkout_are_private(self):
        for path in ('/sr/cart/', '/sr/checkout/', '/sr/cart', '/sr/account/orders/'):
            with self.subTest(path=path):
                self.assertTrue(_is_private(path))
        self.assertFalse(_is_private('/sr/returns/'))
        self.assertFalse(_is_private('/sr/'))

    def test_the_serbian_cart_says_noindex_and_names_no_alternates(self):
        body = self.client.get('/sr/cart/').content.decode()
        robots = re.findall(r'<meta name="robots" content="([^"]+)"', body)
        self.assertEqual(len(robots), 1)
        self.assertIn('noindex', robots[0])
        self.assertNotIn('hreflang=', body.split('</head>', 1)[0])

    def test_robots_txt_blocks_the_prefixed_copies(self):
        lines = render_robots_txt().splitlines()
        self.assertIn('Disallow: /cart/', lines)
        self.assertIn('Disallow: /sr/cart/', lines)
        self.assertIn('Disallow: /sr/checkout/', lines)
        # Sign-in has one address in every language: no copy of it.
        self.assertIn('Disallow: /auth/', lines)
        self.assertNotIn('Disallow: /sr/auth/', lines)


@override_settings(LANGUAGES=[('en', 'English')], LANGUAGE_CODE='en')
class OneLanguageStoreTests(TestCase):
    def test_a_store_with_one_language_gets_no_copies(self):
        self.assertNotIn('Disallow: /en/', render_robots_txt())
