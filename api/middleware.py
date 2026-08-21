import hashlib
import json
import logging

from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger('morpheus.api.cache')

# Deny-by-default allowlist of root Query fields safe to share across anonymous
# visitors. ONLY public, non-personalized catalog reads — a query whose every
# top-level field is in here is cacheable; anything else (cart/cartTotals,
# scope-gated cmsPage, the personalized semanticSearch, or a field added later)
# falls through uncached. Fails safe: a renamed field drops out of the set and
# simply stops being cached, never leaks.
_CACHEABLE_ROOT_FIELDS = frozenset(
    {'product', 'products', 'collections', 'categories', 'bookProduct'}
)


def _cacheable_query(query: str) -> bool:
    """True iff `query` is a pure query whose top-level fields are all public
    catalog reads. Parse-based (not substring) so it can't be fooled, and
    fail-closed: any parse error or non-query operation → not cacheable."""
    try:
        from graphql import parse
        from graphql.language.ast import FieldNode, OperationDefinitionNode

        document = parse(query)
    except Exception:  # noqa: BLE001 — unparseable → let Strawberry report it, don't cache
        return False
    saw_operation = False
    for definition in document.definitions:
        if not isinstance(definition, OperationDefinitionNode):
            continue
        saw_operation = True
        if definition.operation.value != 'query':
            return False  # mutation / subscription
        for selection in definition.selection_set.selections:
            if not isinstance(selection, FieldNode):
                return False  # a fragment spread at the root — can't verify cheaply
            if selection.name.value not in _CACHEABLE_ROOT_FIELDS:
                return False
    return saw_operation


def _vary_key(request) -> dict:
    """The per-visitor axes an anonymous storefront response varies on. Folded
    into the cache key so an EUR/`/fr/` visitor's response is never served to a
    USD/`/en/` one (a shared query+variables-only key poisoned across visitors)."""
    market = getattr(request, 'market', None)
    market_key = str(getattr(market, 'pk', '') or getattr(market, 'code', '') or '')
    currency = ''
    session = getattr(request, 'session', None)
    if session is not None:
        currency = str(session.get('display_currency') or '')
    try:
        from django.utils.translation import get_language

        lang = get_language() or ''
    except Exception:  # noqa: BLE001
        lang = ''
    return {'market': market_key, 'currency': currency, 'lang': lang}


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

            # Deny-by-default: cache ONLY a pure query whose every top-level field
            # is a public catalog read (_CACHEABLE_ROOT_FIELDS). This replaces the
            # old `'cart' in query` substring guard — which was both too broad and
            # too narrow — and inherently excludes mutations, introspection, the
            # session-scoped cart/cartTotals/shippingRates family, and any
            # personalized or future field.
            if not query or not _cacheable_query(query):
                return self.get_response(request)

            variables = body.get('variables', {})

            # Key on query+variables AND the per-visitor vary axes (market /
            # currency / language) — without them an anonymous EUR/`/fr/`
            # visitor's response would be replayed to the next USD/`/en/` guest.
            cache_data = {'query': query, 'variables': variables, 'vary': _vary_key(request)}
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
