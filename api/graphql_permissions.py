"""
GraphQL permission helpers.

Strawberry doesn't ship a uniform permissions system, so we use plain helpers
that resolvers call early. They look at:

1. `request.user` (Django session/Token auth)
2. `request._morpheus_api_key` (DRF API key auth, set by MorpheusAPIKeyAuthentication)
3. `request.agent_capabilities` (set by AgentAuthMiddleware on /graphql/agent/)

A request is considered "anonymous" if none of these grant the requested scope.
"""

from __future__ import annotations

import logging
from typing import Any

import strawberry

logger = logging.getLogger('morpheus.api.graphql.auth')


class PermissionDenied(Exception):
    """Raised when a resolver detects an unauthorized caller."""


def get_request(info: strawberry.Info) -> Any | None:
    if not info or not info.context:
        return None
    if isinstance(info.context, dict):
        return info.context.get('request')
    return getattr(info.context, 'request', None)


def is_authenticated(info: strawberry.Info) -> bool:
    """True for any authenticated principal (session user, token, API key, agent)."""
    request = get_request(info)
    if not request:
        return False
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return True
    if getattr(request, '_morpheus_api_key', None) is not None:
        return True
    if getattr(request, 'agent_capabilities', None) is not None:  # noqa: SIM103
        return True
    return False


def is_staff(info: strawberry.Info) -> bool:
    """True when the request principal is a staff user."""
    request = get_request(info)
    user = getattr(request, 'user', None) if request else None
    return bool(user and getattr(user, 'is_staff', False))


def has_scope(info: strawberry.Info, scope: str) -> bool:
    """True when the caller has the given scope, or admin/staff equivalence."""
    request = get_request(info)
    if not request:
        return False

    api_key = getattr(request, '_morpheus_api_key', None)
    if api_key and api_key.has_scope(scope):
        return True

    caps = getattr(request, 'agent_capabilities', None)
    if caps and (scope in caps.get('scopes', []) or 'admin' in caps.get('scopes', [])):
        return True

    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):  # noqa: SIM102
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            return True
    return False


def require_scope(info: strawberry.Info, scope: str) -> None:
    """Raise PermissionDenied unless the caller has the scope."""
    if not has_scope(info, scope):
        raise PermissionDenied(f'Missing required scope: {scope}')


def require_authenticated(info: strawberry.Info) -> None:
    if not is_authenticated(info):
        raise PermissionDenied('Authentication required')


def current_customer(info: strawberry.Info):
    """Return the logged-in Customer or None (no exception)."""
    request = get_request(info)
    if not request:
        return None
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


def current_channel_id(info: strawberry.Info):
    """Channel scoping for multi-tenant resolvers — returns None when unscoped."""
    request = get_request(info)
    if not request:
        return None
    api_key = getattr(request, '_morpheus_api_key', None)
    if api_key and getattr(api_key, 'channel_id', None):
        return api_key.channel_id
    caps = getattr(request, 'agent_capabilities', None)
    if caps and caps.get('channel_id'):
        return caps['channel_id']
    return None
