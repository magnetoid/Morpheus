"""Bearer/scope auth for the ACP surface.

We reuse ``agent_mcp``'s token store + resolution wholesale — same
``PluginConfig['agent_mcp']['public_keys']`` Bearer tokens that gate MCP and
GraphQL. ACP endpoints require a *valid* token AND the ``acp.checkout`` scope.

``require_acp_scope(request, scope)`` is the single entry point a view calls
before doing any work. It returns ``None`` when the caller is authorised, or a
ready-to-return ``JsonResponse`` (401/403) when not — mirroring how the MCP
server gates ``tools/call`` and the GraphQL endpoint gates mutations.

ACP is a payment-adjacent surface, so unlike the MCP/GraphQL surfaces it does
NOT inherit the wildcard: a token is granted ACP access **only** when it
carries an explicit ``acp_scopes`` list containing ``acp.checkout``. A legacy
raw-string token or a dict token missing the ``acp_scopes`` key gets NO access
here — explicit opt-in, so no existing token silently gains checkout rights.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse

from plugins.installed.agentic_checkout.serializers import error_response

# Required scope for every ACP checkout-session endpoint.
ACP_SCOPE = 'acp.checkout'


def _acp_granted(entry) -> set[str]:
    """ACP scope set for a token entry — explicit opt-in, NO wildcard.

    Returns the literal ``acp_scopes`` list only. A legacy raw-string token or
    a dict entry without an ``acp_scopes`` key returns the empty set (no ACP
    access), so the wildcard that the MCP/GraphQL surfaces grant never leaks
    onto this payment-adjacent surface.
    """
    if not isinstance(entry, dict):
        return set()
    val = entry.get('acp_scopes')
    if not isinstance(val, (list, tuple, set)):
        return set()
    return {str(s).strip() for s in val if s}


def _bearer_token(request: HttpRequest) -> str:
    auth = request.headers.get('Authorization', '')
    if not auth.lower().startswith('bearer '):
        return ''
    return auth.split(' ', 1)[1].strip()


def require_acp_scope(request: HttpRequest, scope: str = ACP_SCOPE) -> JsonResponse | None:
    """Gate an ACP request. Returns ``None`` when authorised, else a 401/403.

    * No / malformed ``Authorization`` header, or unknown token → 401.
    * Valid token missing the required scope → 403.
    """
    from plugins.installed.agent_mcp.auth import apply_bearer_user
    from plugins.installed.agent_mcp.scopes import find_entry_for_token, has_any

    token = _bearer_token(request)
    if not token:
        return error_response(
            'unauthorized',
            'Missing Bearer token.',
            status=401,
        )

    # apply_bearer_user validates the token against the agent_mcp store and,
    # on success, swaps request.user for the synthetic service user.
    if not apply_bearer_user(request):
        return error_response(
            'unauthorized',
            'Invalid or unknown Bearer token.',
            status=401,
        )

    entry = find_entry_for_token(token)
    granted = _acp_granted(entry)
    if not has_any(granted, [scope]):
        return error_response(
            'forbidden',
            f'Token missing required scope: {scope}.',
            status=403,
        )
    return None
