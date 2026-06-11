"""
Internal GraphQL client — lets storefront views query the API
without going through HTTP. Never bypass this to use ORM directly.
"""

from strawberry.types import ExecutionResult


class GraphQLExecutionError(Exception):
    """Raised when internal GraphQL execution returns errors."""

    def __init__(self, errors):
        self.errors = errors
        error_msgs = [str(e) for e in errors]
        super().__init__(f'GraphQL Execution Errors: {", ".join(error_msgs)}')


def internal_graphql(query: str, variables: dict | None = None, request=None) -> dict:
    """
    Execute a GraphQL query against the internal schema.
    Returns the data dict directly. Raises GraphQLExecutionError on schema/execution errors.
    """
    from api.schema import get_schema

    schema = get_schema()
    context = {'request': request}
    result: ExecutionResult = schema.execute_sync(
        query,
        variable_values=variables or {},
        context_value=context,
    )
    if result.errors:
        import logging

        logging.getLogger('morpheus.api.client').error(f'Internal GraphQL errors: {result.errors}')
        raise GraphQLExecutionError(result.errors)
    return result.data or {}
