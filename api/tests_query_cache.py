"""A repeated GraphQL query is parsed and validated once, not on every call.

Parse + validate cost ~4.7 ms per call against this schema (measured 2026-10-14), and
every storefront page sends the same fixed query strings through internal_graphql.
"""

from __future__ import annotations

from django.test import TestCase


class QueryCacheTests(TestCase):
    def test_a_repeated_query_hits_the_parse_and_validation_caches(self):
        from strawberry.extensions.parser_cache import _get_parse_cache
        from strawberry.extensions.validation_cache import _get_validate_cache

        from api.client import internal_graphql
        from api.schema import QUERY_CACHE_SIZE

        parse, validate = _get_parse_cache(QUERY_CACHE_SIZE), _get_validate_cache(QUERY_CACHE_SIZE)
        query = 'query { products(first: 1) { slug } }'
        internal_graphql(query)
        parsed, validated = parse.cache_info().hits, validate.cache_info().hits
        internal_graphql(query)
        self.assertEqual(parse.cache_info().hits, parsed + 1)
        self.assertEqual(validate.cache_info().hits, validated + 1)
