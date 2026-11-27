"""The two cache layers never disagree about a page that is one visitor's.

`core.storefront_cache.StorefrontCacheMiddleware` (outermost) applies the header a
merchant saves on Settings -> Caching; the storefront app's own middleware (inner)
sends its public header only on a list of shared pages and never to a visitor
with a session, cart or consent cookie. The outer layer checked neither, so once a
store saved the Caching page, an anonymous /cart/ and a page rendered for a
visitor's consent choice went out `public, s-maxage=300`: a CDN then served them
to everyone. Both layers now read one rule, `core.storefront_cache.may_be_public`.
"""

from __future__ import annotations

import json

from django.test import TestCase

from plugins.testing import set_app_settings

#: What the Caching page pre-fills, saved the way its form saves it.
_SAVED = (
    'public, max-age=0, s-maxage=300, must-revalidate, '
    'stale-while-revalidate=86400, stale-if-error=86400'
)


class CacheLayersAgreeTests(TestCase):
    def setUp(self):
        set_app_settings(self, 'storefront', html_cache_control=_SAVED)

    def _cache_control(self, path, **cookies):
        for name, value in cookies.items():
            self.client.cookies[name] = value
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get('Cache-Control', '')

    def test_an_anonymous_cart_is_never_public(self):
        self.assertNotIn('public', self._cache_control('/cart/'))

    def test_a_page_rendered_for_a_consent_choice_is_never_public(self):
        consent = json.dumps({'analytics': True})
        self.assertNotIn('public', self._cache_control('/products/', morpheus_consent=consent))

    def test_a_visitor_with_a_cart_never_gets_a_public_page(self):
        self.assertNotIn('public', self._cache_control('/about/', cart_token='abc'))

    def test_a_shared_page_still_gets_the_saved_header(self):
        self.assertEqual(self._cache_control('/search/'), _SAVED)
