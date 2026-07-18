import hashlib
import json
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('morpheus.api.cache')


class GraphQLCacheMiddleware:
    """
    Enterprise GraphQL Query Caching Middleware.
    Intercepts POST requests to /graphql/. If the body contains a read-only query
    (no mutations) and it exists in Redis, returns the cached JSON response instantly,
    bypassing the entire Django ORM and Strawberry GraphQL execution layer.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):  # noqa: PLR0911
        if not request.path.startswith('/graphql'):
            return self.get_response(request)

        if request.method != 'POST':
            return self.get_response(request)

        # Never cache for authenticated callers — the cache key is only
        # query+variables, so a shared entry would replay one user's
        # (authorization-dependent) result to everybody. This middleware sits
        # after AuthenticationMiddleware/AgentAuthMiddleware, so request.user
        # is resolved; the Authorization-header check also skips bearer-token
        # agents whatever their user resolution. Anonymous storefront traffic
        # (the hot path this cache exists for) still gets the 5-min cache.
        user = getattr(request, 'user', None)
        if (user is not None and getattr(user, 'is_authenticated', False)) or request.headers.get(
            'Authorization'
        ):
            return self.get_response(request)

        try:
            body = json.loads(request.body)
            query = body.get('query', '')

            # Never cache mutations or introspection queries
            if not query or 'mutation' in query.strip().lower()[:20] or '__schema' in query:
                return self.get_response(request)

            variables = body.get('variables', {})

            # Create a unique SHA-256 hash for this specific query + variables combination
            cache_data = {'query': query, 'variables': variables}
            hash_key = hashlib.sha256(
                json.dumps(cache_data, sort_keys=True).encode('utf-8')
            ).hexdigest()
            cache_key = f'graphql:query:{hash_key}'

            # Attempt to fetch from Redis
            cached_result = cache.get(cache_key)
            if cached_result:
                logger.debug(f'GraphQL Cache HIT: {hash_key}')
                return JsonResponse(cached_result)

            logger.debug(f'GraphQL Cache MISS: {hash_key}')

            # Execute the actual Strawberry GraphQL request
            response = self.get_response(request)

            # If successful (200 OK) and no GraphQL errors, cache the result for 5 minutes
            if response.status_code == 200:
                response_content = json.loads(response.content)
                if not response_content.get('errors'):
                    cache.set(cache_key, response_content, timeout=300)
                    logger.debug(f'GraphQL Cache SET: {hash_key}')

            return response

        except json.JSONDecodeError:
            # Malformed JSON, let Strawberry handle the error
            return self.get_response(request)
        except Exception as e:
            logger.error(f'GraphQL Cache Error: {e}')
            return self.get_response(request)
