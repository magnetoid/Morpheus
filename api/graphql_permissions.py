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


# GraphQL scope → RBAC capability. The two vocabularies grew separately: scopes
# gate API tokens, capabilities gate dashboard roles. Mapping them is what makes
# a role change in the dashboard reach the GraphQL surface at all. A scope with
# no entry keeps the previous is_staff behaviour, so adding a resolver can never
# accidentally deny; `vendor:self` is deliberately absent (it describes a
# customer-owned relation, not a staff capability).
_CAPABILITY_FOR_SCOPE = {
    'admin:seo': 'seo.write',
    'cms.read': 'cms.read',
    'cms.write': 'cms.write',
    'catalog.read': 'catalog.read',
    'catalog.write': 'catalog.write',
    'read:orders': 'orders.read',
    'read:carts': 'orders.read',
    'read:metrics': 'analytics.read',
    'read:environments': 'system.read',
    'read:functions': 'system.read',
    'write:functions': 'system.write',
    'i18n.read': 'system.read',
    'i18n.write': 'system.write',
    'admin:cloudflare': 'system.write',
    'admin:marketplace': 'system.write',
    'admin:affiliates': 'affiliates.write',
}


def has_scope(info: strawberry.Info, scope: str) -> bool:  # noqa: PLR0911
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

    # A Bearer MCP/agent token resolves to a SHARED is_staff=True service user
    # (agent_mcp.auth._service_user), so the is_staff fallback below would grant
    # EVERY scope to ANY valid token — a token minted with only catalog.read
    # would pass admin:seo, read:orders, cms.write, … The token stashes its own
    # per-surface scope set; when that is present, authorize against it ALONE
    # and never fall through to is_staff. Absence of the attribute means no
    # token was applied → a genuine session-authenticated staff user, who keeps
    # the is_staff fallback (they hold the same power in the dashboard).
    tok_scopes = getattr(request, '_morph_token_scopes_graphql', None)
    if tok_scopes is not None:
        # has_any honours the wildcard (legacy/unconfigured tokens) and denies
        # a scoped token that lacks this scope.
        from plugins.installed.agent_mcp.scopes import has_any

        return has_any(tok_scopes, [scope])

    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):  # noqa: SIM102
        if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
            # Session-authenticated staff. Route through the RBAC capability seam
            # rather than granting on is_staff alone, so a merchant's role
            # revocation actually reaches the API — GraphQL consulted
            # core/authz.py NOWHERE before this, which meant a role stripped in
            # the dashboard still had full GraphQL access.
            #
            # `check()` is MODE-AWARE and that is the whole point: under the
            # default `log` mode a failed check still returns True while
            # recording the would-be denial, so this changes NO behaviour today
            # and starts denying only when the merchant flips enforcement.
            # (`has_capability()` would deny immediately — never use it here.)
            capability = _CAPABILITY_FOR_SCOPE.get(scope)
            if capability:
                from core.authz import check

                return check(user, capability, target=f'graphql:{scope}')
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
