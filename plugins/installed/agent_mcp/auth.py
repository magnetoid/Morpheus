"""Bearer-token authentication for staff-only HTTP surfaces.

The MCP admin server (``views._is_authed``) already uses
``PluginConfig['agent_mcp']['public_keys']`` to gate access. This
module exposes a second consumer: the GraphQL endpoint at
``/graphql/`` so external agents can call mutations without managing
Django session cookies.

``apply_bearer_user(request)`` is the single entry point. Call it from
a view (or middleware) before any code that checks
``request.user.is_staff``. If a valid Bearer token is presented,
``request.user`` is replaced with a service Customer that has
``is_staff=True``. If no token / invalid token, the function is a
no-op — Django's session-cookie auth keeps working as before.

Tokens stay valid until the merchant revokes them from
``/dashboard/apps/agent_mcp/tokens/``. Every successful resolve writes
the current timestamp back to the matching token entry's
``last_used_at`` (best-effort; never raises).
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any

from django.http import HttpRequest

logger = logging.getLogger('morpheus.agent_mcp.auth')

# Reserved username/email for the synthetic service account. Anything
# Bearer-authenticated runs as this user; staff filters + audit logs
# attribute the action to ``service@morpheus.internal`` — easy to spot
# in admin event lists.
_SERVICE_USERNAME = 'mcp-service'
_SERVICE_EMAIL = 'service@morpheus.internal'


def _present_token(request: HttpRequest) -> str:
    auth = request.headers.get('Authorization', '')
    if not auth.lower().startswith('bearer '):
        return ''
    return auth.split(' ', 1)[1].strip()


def _service_user():
    """Get or lazily create the synthetic Bearer-auth service user."""
    from plugins.installed.customers.models import Customer

    user, created = Customer.objects.get_or_create(
        username=_SERVICE_USERNAME,
        defaults={
            'email': _SERVICE_EMAIL,
            'is_staff': True,
            'is_active': True,
        },
    )
    # Defensive: if a previous merchant flipped these off, re-flip.
    # Without is_staff=True the GraphQL mutations would reject the
    # request even though the token is valid.
    changed: list[str] = []
    if not user.is_staff:
        user.is_staff = True
        changed.append('is_staff')
    if not user.is_active:
        user.is_active = True
        changed.append('is_active')
    if not user.has_usable_password():
        user.set_unusable_password()
        changed.append('password')
    if changed:
        user.save(update_fields=changed)
    return user


def _touch_last_used(token: str) -> None:
    """Best-effort update of the token's last_used_at timestamp."""
    try:
        from plugins.models import PluginConfig

        cfg = PluginConfig.objects.filter(plugin_name='agent_mcp').first()
        if cfg is None:
            return
        config = dict(cfg.config or {})
        entries: list[Any] = list(config.get('public_keys') or [])
        now = _dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z'
        changed = False
        for i, e in enumerate(entries):
            if isinstance(e, dict) and (e.get('token') or '').strip() == token:
                e['last_used_at'] = now
                entries[i] = e
                changed = True
                break
        if changed:
            config['public_keys'] = entries
            cfg.config = config
            cfg.save(update_fields=['config', 'updated_at'])
    except Exception as e:  # noqa: BLE001 — never break the request on a stat write
        logger.debug('agent_mcp: last_used_at write failed: %s', e)


def apply_bearer_user(request: HttpRequest) -> bool:
    """Resolve a Bearer token to a staff service user on `request.user`.

    Returns True when a valid token was applied, False otherwise (and
    in that case `request.user` is left as-is — Django's session
    middleware decides what happens).

    Also stashes the token's per-surface scope sets on the request so
    downstream checks can authorise without re-looking up the entry:

      request._morph_token_scopes_mcp     : set[str]
      request._morph_token_scopes_graphql : set[str]
      request._morph_token_label          : str (for audit logs)

    Legacy raw-string tokens get the wildcard set on both surfaces —
    fully backward-compatible.
    """
    token = _present_token(request)
    if not token:
        # No Bearer token: leave the request UNTOUCHED. A session-authenticated
        # staff user (the dashboard's own GraphQL/console path) must keep the
        # downstream is_staff fallback — stashing empty sets here would deny it.
        return False
    # A token WAS presented. From here every exit denies: stash EMPTY scope
    # sets before any fallible work, so a half-completed resolution (an invalid
    # token, a raised _service_user, a DB blip) can never fall through to a
    # WILDCARD default downstream. Only a fully successful resolution widens.
    request._morph_token_scopes_mcp = set()
    request._morph_token_scopes_graphql = set()
    request._morph_token_approved_tools = set()
    request._morph_token_rate_limit = None

    # Re-use the same source-of-truth reader as the MCP server.
    from plugins.installed.agent_mcp.views import _api_keys

    if token not in _api_keys():
        return False
    try:
        request.user = _service_user()
    except Exception as e:  # noqa: BLE001 — log + fall through to session auth
        logger.warning('agent_mcp: bearer resolve failed: %s', e, exc_info=True)
        return False
    # Attach per-surface scope sets. Legacy entries (raw strings) get
    # the wildcard automatically via token_scopes().
    from plugins.installed.agent_mcp.scopes import find_entry_for_token, token_scopes

    entry = find_entry_for_token(token)
    request._morph_token_scopes_mcp = token_scopes(entry, 'mcp')
    request._morph_token_scopes_graphql = token_scopes(entry, 'graphql')
    request._morph_token_label = (entry or {}).get('label', '') if isinstance(entry, dict) else ''
    # Governance metadata (enterprise Phase 1): which requires_approval tools
    # the merchant pre-approved THIS token for, and its per-minute rate limit.
    # Legacy raw-string tokens get neither (deny-by-default on approval tools).
    if isinstance(entry, dict):
        request._morph_token_approved_tools = {str(t) for t in (entry.get('approved_tools') or [])}
        try:
            request._morph_token_rate_limit = int(entry.get('rate_limit_per_minute') or 0) or None
        except (TypeError, ValueError):
            request._morph_token_rate_limit = None
    else:
        request._morph_token_approved_tools = set()
        request._morph_token_rate_limit = None
    _touch_last_used(token)
    return True
