"""GraphQL cache must never serve one caller's result to another.

The cache key is query+variables only, so the middleware may cache ONLY
anonymous, token-less traffic. An authenticated request (session user or
Authorization header) must bypass the cache in both directions — never
read a shared entry, never write one. Exercised at the middleware layer
with a stub downstream so no schema execution is involved.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from api.middleware import GraphQLCacheMiddleware

# A public, allowlisted catalog read (the kind this cache exists for).
_QUERY = {'query': 'query Q { products { id name } }', 'variables': {}}


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class GraphQLCacheIsolationTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # locmem persists across test methods — isolate each
        self.factory = RequestFactory()
        self.calls = 0

        def downstream(request):
            self.calls += 1
            return JsonResponse({'data': {'call': self.calls}})

        self.mw = GraphQLCacheMiddleware(downstream)

    def _post(self, *, user=None, auth_header=''):
        extra = {'HTTP_AUTHORIZATION': auth_header} if auth_header else {}
        request = self.factory.post(
            '/graphql/', data=json.dumps(_QUERY), content_type='application/json', **extra
        )
        request.user = user if user is not None else AnonymousUser()
        return self.mw(request)

    def _post_query(self, query):
        request = self.factory.post(
            '/graphql/', data=json.dumps({'query': query}), content_type='application/json'
        )
        request.user = AnonymousUser()
        return self.mw(request)

    def test_anonymous_requests_are_cached(self):
        self._post()
        self._post()
        self.assertEqual(self.calls, 1)  # second hit served from cache

    def test_cart_query_never_cached(self):
        # Session-scoped: `cart` resolves from request.session — a shared cache
        # entry would leak one guest's cart (incl. gift-card codes) to the next.
        self._post_query('query { cart { id items { quantity } } }')
        self._post_query('query { cart { id items { quantity } } }')
        self.assertEqual(self.calls, 2)  # every cart query hits downstream

    def test_shipping_rates_query_never_cached(self):
        # shippingRates(cartId:) is per-cart / reads session — never cache it.
        q = 'query { shippingRates(cartId: "x") { name } }'
        self._post_query(q)
        self._post_query(q)
        self.assertEqual(self.calls, 2)

    def test_authenticated_request_bypasses_cache_both_ways(self):
        user = get_user_model().objects.create_user(
            username='u1', email='u1@example.com', password='x'
        )
        # prime the cache anonymously…
        self._post()
        self.assertEqual(self.calls, 1)
        # …an authenticated caller must NOT be served that shared entry
        self._post(user=user)
        self.assertEqual(self.calls, 2)
        # …and must not have written one another user could read
        user2 = get_user_model().objects.create_user(
            username='u2', email='u2@example.com', password='x'
        )
        self._post(user=user2)
        self.assertEqual(self.calls, 3)

    def test_bearer_token_request_bypasses_cache(self):
        self._post()  # primes the anonymous entry
        self._post(auth_header='Bearer sk-agent-token')
        self.assertEqual(self.calls, 2)  # not served from the shared entry

    def test_non_catalog_query_is_not_cached(self):
        # Deny-by-default: a field not on the public catalog allowlist (here a
        # personalized one) must never be cached, even for anonymous callers.
        self._post_query('query { semanticSearch(query: "x") { results } }')
        self._post_query('query { semanticSearch(query: "x") { results } }')
        self.assertEqual(self.calls, 2)

    def _post_varying(self, *, currency='', market_pk='', lang='en'):
        request = self.factory.post(
            '/graphql/', data=json.dumps(_QUERY), content_type='application/json'
        )
        request.user = AnonymousUser()
        request.session = {'display_currency': currency} if currency else {}
        if market_pk:
            request.market = type('M', (), {'pk': market_pk})()
        from django.utils import translation

        with translation.override(lang):
            return self.mw(request)

    def test_currency_varies_the_cache_key(self):
        # The whole bug: two anonymous guests differing only in display currency
        # must NOT share a cache entry (one would be shown the other's prices).
        self._post_varying(currency='USD')
        self._post_varying(currency='EUR')
        self.assertEqual(self.calls, 2, 'USD and EUR guests shared a cache entry')
        # …but two USD guests DO share (the cache still works within an axis).
        self._post_varying(currency='USD')
        self.assertEqual(self.calls, 2)

    def test_market_and_language_vary_the_cache_key(self):
        self._post_varying(market_pk='1', lang='en')
        self._post_varying(market_pk='2', lang='en')
        self.assertEqual(self.calls, 2, 'different markets shared a cache entry')
        self._post_varying(market_pk='1', lang='fr')
        self.assertEqual(self.calls, 3, 'different languages shared a cache entry')
