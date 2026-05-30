import logging

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from core.models import APIKey

logger = logging.getLogger('morpheus.api.auth')


class AgentAuthMiddleware(MiddlewareMixin):
    """Authenticate Agent-to-Agent (A2A) Protocol requests on /graphql/agent/.

    Two acceptable token stores — the middleware tries both so tokens
    minted via either path work without a sync step:

    1. ``core.APIKey`` row (``is_active=True``) — hand-issued from the
       shell or via a future admin form. Scopes live on the row.
    2. ``PluginConfig['agent_mcp']['public_keys']`` entry — what the
       merchant UI at /dashboard/apps/agent_mcp/tokens/ actually
       writes to. The same lookup the MCP RPC endpoints use, so a
       token minted in the UI now works on /graphql/agent/ too.

    Without the fallback (path 2) the merchant UI's "Create token"
    button produced tokens that returned 401 here while working fine
    on /mcp/admin/v1/ — confusing and a sign of two unsynced stores.
    """

    def process_request(self, request):
        # We only care about requests hitting the agent endpoint
        if not request.path.startswith('/graphql/agent/'):
            return None

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse(
                {'error': 'Unauthorized: Missing or invalid Bearer token'}, status=401
            )

        token = auth_header.split(' ', 1)[1].strip()

        # Path 1 — core.APIKey table (legacy / shell-issued).
        try:
            api_key = APIKey.objects.get(key=token, is_active=True)
            request.agent_capabilities = {
                'scopes': api_key.scopes,
                'channel_id': str(api_key.channel_id) if api_key.channel else None,
                'is_agent': True,
            }
            logger.info('Authenticated agent: %s', api_key.name)
            return None
        except APIKey.DoesNotExist:
            pass

        # Path 2 — PluginConfig store (what the dashboard UI writes).
        # apply_bearer_user resolves the token, sets request.user to the
        # service user, stamps last_used_at, and stashes per-surface
        # scope sets on the request. We only need the graphql scopes
        # to project into agent_capabilities for legacy callers.
        try:
            # PLC0415 tolerated: cross-plugin import is intentional to
            # avoid an import-time cycle (agent_mcp imports api too).
            from plugins.installed.agent_mcp.auth import apply_bearer_user  # noqa: PLC0415

            if apply_bearer_user(request):
                gql_scopes = getattr(request, '_morph_token_scopes_graphql', set()) or set()
                request.agent_capabilities = {
                    'scopes': sorted(gql_scopes) if gql_scopes else ['*'],
                    'channel_id': None,
                    'is_agent': True,
                }
                label = getattr(request, '_morph_token_label', '') or '(unlabelled)'
                logger.info('Authenticated MCP token: %s', label)
                return None
        except Exception as e:  # noqa: BLE001 — never let MCP-side import errors break auth
            logger.warning('agent_auth: MCP fallback failed: %s', e, exc_info=True)

        return JsonResponse({'error': 'Unauthorized: Invalid Agent Token'}, status=401)
