"""Cache invalidation must delete the keys the cache actually writes.

This is a contract between two files that never import each other:
`api/cache.py` chooses the key format, `core/utils/cache.py` chooses what to
delete. Nothing connects them, so they drifted — the invalidator spent a long
time deleting `gql:*product*`, which nothing has ever written. Every product
edit "invalidated" zero keys and the API kept serving the old price until the
TTL lapsed.

It only misbehaved in production: `delete_pattern` exists on django-redis, and
local dev/test uses LocMem, which has no such method and falls through to
`cache.clear()` — so development always looked correct.
"""

from __future__ import annotations

import fnmatch

from django.test import SimpleTestCase

from core.utils.cache import SmartCacheInvalidator


class CacheKeyContractTests(SimpleTestCase):
    def _graphql_key(self) -> str:
        """Build a key exactly as api/middleware.py (the REAL writer) does."""
        import hashlib

        hash_key = hashlib.sha256(b'{ products { id } }|{}').hexdigest()
        return f'graphql:query:{hash_key}'

    def test_the_invalidator_matches_a_real_graphql_cache_key(self):
        key = self._graphql_key()
        patterns = SmartCacheInvalidator._QUERY_CACHE_PATTERNS
        self.assertTrue(
            any(fnmatch.fnmatch(key, p) for p in patterns),
            f'no invalidation pattern matches {key!r}; patterns={patterns}. '
            f'A product edit would leave this entry stale until its TTL.',
        )

    def test_the_key_format_has_not_moved(self):
        """Guard the REAL writer. The cache is written by the GraphQL cache
        MIDDLEWARE (api/middleware.py); the old api/cache.py SchemaExtension
        was never wired into api/schema.py's extensions list — dead code that
        this test used to read, so a middleware key change would have gone
        uncaught while every product-edit purge matched zero keys."""
        import pathlib

        from django.conf import settings

        src = (pathlib.Path(settings.BASE_DIR) / 'api' / 'middleware.py').read_text(
            encoding='utf-8'
        )
        self.assertIn(
            "f'graphql:query:{hash_key}'",
            src,
            'api/middleware.py changed its key format — update '
            'SmartCacheInvalidator._QUERY_CACHE_PATTERNS to match.',
        )

    def test_locmem_fallback_clears_everything(self):
        """Dev/test has no delete_pattern; the fallback must still invalidate."""
        from django.core.cache import cache

        cache.set('graphql:query:abc', 'stale', 60)
        SmartCacheInvalidator._clear_query_caches('test')
        self.assertIsNone(cache.get('graphql:query:abc'))
