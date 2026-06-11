"""Agent-discovery files served from /.well-known/.

Two endpoints:

  /.well-known/ucp.json    Universal Commerce Protocol manifest.
                           Spec: a Google + Shopify + Stripe + Etsy +
                           Walmart open extension on top of MCP that
                           lets a single agent (Gemini, ChatGPT, Comet)
                           discover a merchant's commerce surface
                           without a per-vendor integration.

  /.well-known/agent.json  Trusted Agent Protocol (Visa) / Verifiable
                           Intent (Mastercard) capabilities manifest.
                           Both ride on Web Bot Auth — Cloudflare
                           verifies signed agent traffic at the edge
                           and stamps `X-Verified-Agent-*` headers.
                           This manifest tells the agent registry
                           which capabilities our endpoint supports.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(['GET'])
def ucp_manifest(request: HttpRequest) -> JsonResponse:
    base = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(
        {
            'protocolVersion': '1.0',
            'name': 'morpheus-ucp',
            'description': 'Universal Commerce Protocol — Morpheus storefront.',
            'capabilities': {
                'productSearch': True,
                'productDetails': True,
                'cart': True,
                'checkout': True,
                'orderStatus': True,
                'returns': False,
                'subscriptions': False,
            },
            'mcp': {
                'storefront': f'{base}/mcp/storefront/v1/',
                'cart': f'{base}/mcp/cart/v1/',
                'checkout': f'{base}/mcp/checkout/v1/',
            },
            'compat': ['mcp', 'mcp-streamable', 'a2a'],
            'auth': {
                'type': 'bearer',
                'required_for': ['admin'],
                'registration_url': f'{base}/dashboard/settings/ai/',
            },
            'metadata_url': f'{base}/.well-known/agent.json',
        }
    )


@require_http_methods(['GET'])
def trusted_agent_manifest(request: HttpRequest) -> JsonResponse:
    """Capabilities advertised to Visa TAP / Mastercard Verifiable Intent
    agent registries. Indicates we accept Cloudflare's verified-agent
    header and persist the agent ID on resulting orders."""
    base = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(
        {
            'name': 'morpheus',
            'version': '0.1.0',
            'accepts': {
                'visa_trusted_agent': True,
                'mastercard_verifiable_intent': True,
                'cloudflare_web_bot_auth': True,
            },
            'verification_headers': [
                'X-Verified-Agent-Id',
                'X-Verified-Agent-Provider',
                'X-Verified-Agent-Signature',
            ],
            'persistence': {
                'order.metadata.agent_id': 'persisted on checkout',
                'audit_log': 'AgentRun.metadata + Order.events',
            },
            'mcp_endpoints': {
                'storefront': f'{base}/mcp/storefront/v1/',
                'cart': f'{base}/mcp/cart/v1/',
                'checkout': f'{base}/mcp/checkout/v1/',
            },
            'contact': 'support@morpheus.local',
        }
    )
