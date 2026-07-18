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

_QUERY = {'query': 'query Q { shop { name } }', 'variables': {}}


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

    def test_anonymous_requests_are_cached(self):
        self._post()
        self._post()
        self.assertEqual(self.calls, 1)  # second hit served from cache

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
