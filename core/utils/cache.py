import hashlib
import json
import logging
from functools import wraps

from django.core.cache import cache

from core.hooks import MorpheusEvents, hook_registry

logger = logging.getLogger('morpheus.core.cache')


def cache_graphql_query(timeout=3600, key_prefix='gql'):
    """
    Decorator for Strawberry GraphQL resolvers to cache responses in Redis.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create deterministic cache key from arguments
            # Note: For production, we must also consider request user context
            args_str = json.dumps(kwargs, sort_keys=True)
            key_hash = hashlib.md5(
                f'{func.__name__}:{args_str}'.encode(), usedforsecurity=False
            ).hexdigest()  # noqa: S324
            cache_key = f'{key_prefix}:{func.__name__}:{key_hash}'

            result = cache.get(cache_key)
            if result is not None:
                return result

            # Compute and cache
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result

        return wrapper

    return decorator


class SmartCacheInvalidator:
    """
    Subscribes to the Morpheus Event Bus to automatically invalidate
    Redis caches when models change.
    """

    @staticmethod
    def bind_events():
        # When a product updates, clear product queries
        hook_registry.register(
            MorpheusEvents.PRODUCT_UPDATED, SmartCacheInvalidator._clear_product_cache, priority=10
        )
        hook_registry.register(
            MorpheusEvents.CATEGORY_UPDATED,
            SmartCacheInvalidator._clear_category_cache,
            priority=10,
        )
        logger.info('SmartCacheInvalidator bound to Morpheus Event Bus.')

    # The GraphQL response cache keys every entry `graphql:query:<hash>` — see
    # api/cache.py. The hash is of the query text + variables, so the key says
    # nothing about which entities the response touched: there is no way to
    # invalidate "just the product queries". These patterns must therefore match
    # what api/cache.py actually writes, and clearing is necessarily broad.
    #
    # They previously deleted `gql:*product*` / `rest:*product*` — prefixes
    # nothing has ever written. Every delete matched zero keys, so a product
    # edit left the API serving the old price and title until the TTL lapsed,
    # on production only (local dev has no delete_pattern and falls through to
    # cache.clear(), which is why it never showed up in development).
    _QUERY_CACHE_PATTERNS = ('graphql:query:*', 'rest:*')

    @staticmethod
    def _clear_query_caches(reason: str) -> None:
        if hasattr(cache, 'delete_pattern'):
            for pattern in SmartCacheInvalidator._QUERY_CACHE_PATTERNS:
                cache.delete_pattern(pattern)
        else:
            cache.clear()  # LocMem in dev/tests has no delete_pattern
        logger.info('Invalidated query caches (%s)', reason)

    @staticmethod
    def _clear_product_cache(product, **kwargs):
        SmartCacheInvalidator._clear_query_caches(f'product {getattr(product, "name", "?")}')

    @staticmethod
    def _clear_category_cache(category, **kwargs):
        SmartCacheInvalidator._clear_query_caches(f'category {getattr(category, "name", "?")}')
