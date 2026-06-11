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

    @staticmethod
    def _clear_product_cache(product, **kwargs):
        # In a real Redis cluster, we'd use 'delete_pattern'
        # e.g., cache.delete_pattern("gql:product*")
        logger.info(f'Invalidating Product Cache (triggered by {product.name})')
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('gql:*product*')
            cache.delete_pattern('rest:*product*')
        else:
            cache.clear()  # Fallback for local dev

    @staticmethod
    def _clear_category_cache(category, **kwargs):
        logger.info(f'Invalidating Category Cache (triggered by {category.name})')
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern('gql:*category*')
        else:
            cache.clear()
