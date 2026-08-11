"""
Morpheus CMS — GraphQL Schema Assembly.

Schema is composed from CoreQuery/CoreMutation plus every extension module
registered by an active plugin. Built once at process start (driven from
`api.apps.ApiConfig.ready()`), then served from a process-local cache.
"""

from __future__ import annotations

import importlib
import logging
import threading

import strawberry
from strawberry.extensions import SchemaExtension

from api.graphql_permissions import PermissionDenied

logger = logging.getLogger('morpheus.api')


@strawberry.type
class CoreQuery:
    @strawberry.field(description='Health check')
    def ping(self) -> str:
        return 'pong'

    @strawberry.field(description='Morpheus CMS version')
    def version(self) -> str:
        return '1.0.0'

    @strawberry.field(description='List active plugins')
    def active_plugins(self) -> list[str]:
        from plugins.registry import app_registry

        return [p.name for p in app_registry.active_plugins()]


@strawberry.type
class CoreMutation:
    @strawberry.mutation
    def ping(self) -> str:
        return 'pong'


class _PermissionToGraphQLError(SchemaExtension):
    """Map our PermissionDenied to a structured GraphQL error response."""

    def on_executing_end(self) -> None:  # type: ignore[override]
        result = self.execution_context.result
        if not result or not result.errors:
            return
        for err in result.errors:
            original = getattr(err, 'original_error', None)
            if isinstance(original, PermissionDenied):
                err.message = str(original) or 'Permission denied'
                if err.extensions is None:
                    err.extensions = {}
                err.extensions['code'] = 'PERMISSION_DENIED'


class _MaskUnhandledErrors(SchemaExtension):
    """
    Mask any unhandled exception inside a resolver to `INTERNAL_ERROR` and
    log it with the request_id. Prevents stack traces / model paths from
    leaking through GraphQL responses.

    PermissionDenied + GraphQLError keep their normal behavior (handled
    by `_PermissionToGraphQLError` and Strawberry, respectively).
    """

    def on_executing_end(self) -> None:  # type: ignore[override]
        from graphql import GraphQLError

        from core.request_id import current_request_id

        result = self.execution_context.result
        if not result or not result.errors:
            return
        request_id = current_request_id()
        for err in result.errors:
            original = getattr(err, 'original_error', None)
            if original is None:
                continue
            if isinstance(original, (GraphQLError, PermissionDenied)):
                continue
            logger.error(
                'graphql: unhandled %s in resolver: %s',
                type(original).__name__,
                original,
                exc_info=(type(original), original, original.__traceback__),
                extra={'request_id': request_id},
            )
            try:
                from core.errors.services import record_error  # core (ADR 0025)

                record_error(
                    original,
                    kind='server',
                    extra={'source': 'api.graphql', 'request_id': request_id},
                )
            except Exception:  # noqa: BLE001, S110
                pass
            err.message = 'Internal server error.'
            if err.extensions is None:
                err.extensions = {}
            err.extensions['code'] = 'INTERNAL_ERROR'
            err.extensions['request_id'] = request_id


def build_schema() -> strawberry.Schema:
    """Assemble the schema from core types + all plugin extension modules."""
    from plugins.registry import app_registry

    query_bases = [CoreQuery]
    mutation_bases = [CoreMutation]

    for module_path in app_registry._graphql_extensions:
        try:
            mod = importlib.import_module(module_path)
        except ImportError as e:
            logger.error('Failed to import GraphQL extension %s: %s', module_path, e, exc_info=True)
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if not isinstance(obj, type):
                continue
            if attr_name.endswith('QueryExtension') and obj not in query_bases:
                query_bases.append(obj)
            elif attr_name.endswith('MutationExtension') and obj not in mutation_bases:
                mutation_bases.append(obj)

    @strawberry.type
    class Query(*query_bases):  # type: ignore[misc]
        pass

    @strawberry.type
    class Mutation(*mutation_bases):  # type: ignore[misc]
        pass

    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
        extensions=[_PermissionToGraphQLError, _MaskUnhandledErrors],
    )


_schema_lock = threading.Lock()
_cached_schema: strawberry.Schema | None = None


def get_schema() -> strawberry.Schema:
    global _cached_schema  # noqa: PLW0603
    if _cached_schema is None:
        with _schema_lock:
            if _cached_schema is None:
                _cached_schema = build_schema()
    return _cached_schema


def warm_schema() -> None:
    """Pre-build the schema to remove first-request latency."""
    try:
        get_schema()
    except Exception as e:  # noqa: BLE001 — must not block app startup
        logger.error('Failed to pre-build GraphQL schema: %s', e, exc_info=True)
