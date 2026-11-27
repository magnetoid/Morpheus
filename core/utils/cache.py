import logging

from django.core.cache import cache

from core.hooks import MorpheusEvents, hook_registry

logger = logging.getLogger('morpheus.core.cache')


class SmartCacheInvalidator:
    """
    Subscribes to the Morpheus Event Bus to automatically invalidate
    Redis caches when models change.
    """

    @staticmethod
    def bind_events():
        # Clearing is NECESSARILY broad (the key is a query hash — see below), so
        # bind every event that changes what a cached catalog query would show:
        # a product create/update, a category/collection update, and the
        # stock-state transitions that flip availability in `products`/`product`.
        for event in (
            MorpheusEvents.PRODUCT_CREATED,
            MorpheusEvents.PRODUCT_UPDATED,
            MorpheusEvents.CATEGORY_UPDATED,
            MorpheusEvents.COLLECTION_UPDATED,
            MorpheusEvents.PRODUCT_OUT_OF_STOCK,
            MorpheusEvents.PRODUCT_LOW_STOCK,
        ):
            hook_registry.register(event, SmartCacheInvalidator._clear_catalog_cache, priority=10)
        logger.info('SmartCacheInvalidator bound to Morpheus Event Bus.')

    # The GraphQL response cache keys every entry `graphql:query:<hash>` — the
    # writer is api/middleware.py:GraphQLCacheMiddleware. The hash is of the
    # query text + variables (+ the per-visitor vary axes), so the key says
    # nothing about which entities the response touched: there is no way to
    # invalidate "just the product queries". These patterns must therefore match
    # what the middleware actually writes, and clearing is necessarily broad.
    #
    # They previously deleted `gql:*product*` / `rest:*product*` — prefixes
    # nothing has ever written. Every delete matched zero keys, so a product
    # edit left the API serving the old price and title until the TTL lapsed,
    # on production only (local dev has no delete_pattern and falls through to
    # cache.clear(), which is why it never showed up in development).
    _QUERY_CACHE_PATTERNS = ('graphql:query:*',)

    @staticmethod
    def _clear_query_caches(reason: str) -> None:
        if hasattr(cache, 'delete_pattern'):
            for pattern in SmartCacheInvalidator._QUERY_CACHE_PATTERNS:
                cache.delete_pattern(pattern)
        else:
            cache.clear()  # LocMem in dev/tests has no delete_pattern
        logger.info('Invalidated query caches (%s)', reason)

    @staticmethod
    def _clear_catalog_cache(**kwargs):
        # Bound to product/category/collection/stock events (fire() passes only
        # kwargs). Clearing is broad regardless of which entity changed, so one
        # handler serves them all; name the entity for the log when we can.
        entity = kwargs.get('product') or kwargs.get('category') or kwargs.get('stock_level')
        SmartCacheInvalidator._clear_query_caches(
            f'catalog change: {getattr(entity, "name", None) or type(entity).__name__ if entity else "?"}'
        )
