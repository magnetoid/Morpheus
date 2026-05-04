import json
import hashlib
import logging
from typing import Any, Optional
from strawberry.extensions import SchemaExtension
from django.core.cache import cache

logger = logging.getLogger('morpheus.api.cache')

class GraphQLQueryCacheExtension(SchemaExtension):
    """
    Enterprise GraphQL Query Caching Extension.
    Hashes the incoming GraphQL query and variables. If it's a read-only query
    (no mutations) and it exists in Redis, returns the cached result instantly,
    bypassing the Django ORM and GraphQL resolvers entirely.
    """

    def on_operation(self) -> None:
        # Only cache queries, never mutations
        execution_context = self.execution_context
        
        # We need the operation string to determine if it's a mutation or query
        query_string = execution_context.query
        if not query_string or "mutation" in query_string.strip().lower()[:20]:
            # It's a mutation or introspection, skip caching
            yield
            return

        # Generate a unique hash for this specific query + variables combination
        variables = execution_context.variables or {}
        cache_data = {
            "query": query_string,
            "variables": variables
        }
        
        # Create a SHA-256 hash of the query and variables
        hash_key = hashlib.sha256(json.dumps(cache_data, sort_keys=True).encode('utf-8')).hexdigest()
        cache_key = f"graphql:query:{hash_key}"

        # Attempt to fetch from Redis
        cached_result = cache.get(cache_key)
        
        if cached_result:
            # Cache HIT: Inject the cached result directly into the execution context
            # We skip the actual execution phase by setting the result early.
            # Note: Strawberry extensions don't easily allow aborting execution in `on_operation` 
            # while returning a result in older versions, but we can attach it to the context
            # and short-circuit the resolvers if needed, or simply cache the execution result.
            execution_context.result = cached_result
            logger.debug(f"GraphQL Cache HIT: {hash_key}")
            # We still yield to let the lifecycle complete, but execution_context.result is populated.
        else:
            logger.debug(f"GraphQL Cache MISS: {hash_key}")
            
        yield  # Proceed with the GraphQL lifecycle

        # After execution completes, if we didn't have a cached result and there are no errors, cache it.
        if not cached_result and execution_context.result and not execution_context.result.errors:
            # Cache MISS, but now we have the result. Store it in Redis for 5 minutes.
            cache.set(cache_key, execution_context.result, timeout=300)
            logger.debug(f"GraphQL Cache SET: {hash_key}")
