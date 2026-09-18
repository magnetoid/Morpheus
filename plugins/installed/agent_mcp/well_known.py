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

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from core.utils.site import store_contact_email, store_name, store_slug


def _trusted_agent_enabled() -> bool:
    """True only when the origin actually honors verified-agent headers — i.e.
    the Cloudflare-injected shared secret is configured (TRUSTED_AGENT_PROXY_SECRET).
    Keeps the /.well-known/agent.json `accepts` flags honest: advertising the
    capability while the middleware fail-closed-ignores the headers would be a
    false claim to Visa/Mastercard/Cloudflare agent registries."""
    return bool((getattr(settings, 'TRUSTED_AGENT_PROXY_SECRET', '') or '').strip())


def _capability_live(names) -> bool:
    """True when at least one of the given cluster tool names actually resolves.

    A tool resolves only while its owning plugin is enabled (deactivate drops it
    from the registry), so this is how the manifest advertises cart/checkout as
    true ONLY when agentic_checkout is on — never a dead capability an agent
    would call and get an empty tools/list for.
    """
    try:
        from morpheus.core import agent_registry

        return any(agent_registry.get_tool(n) is not None for n in names)
    except Exception:  # noqa: BLE001 — a resolution hiccup must not 500 the manifest
        return False


@require_http_methods(['GET'])
def ucp_manifest(request: HttpRequest) -> JsonResponse:
    base = request.build_absolute_uri('/').rstrip('/')
    from plugins.installed.agent_mcp.servers import (
        CART_TOOLS,
        CHECKOUT_TOOLS,
        STOREFRONT_TOOLS,
    )

    cart_live = _capability_live(CART_TOOLS - STOREFRONT_TOOLS)
    checkout_live = _capability_live(CHECKOUT_TOOLS - CART_TOOLS)
    return JsonResponse(
        {
            'protocolVersion': '1.0',
            'name': store_slug('ucp'),
            'description': f'Universal Commerce Protocol — {store_name()} storefront.',
            'capabilities': {
                'productSearch': True,
                'productDetails': True,
                # Computed from the live cluster tools (agentic_checkout on/off),
                # not hardcoded — so we never advertise a capability we can't
                # actually serve.
                'cart': cart_live,
                'checkout': checkout_live,
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
                # Anonymous discovery (tools/list) is open on every cluster, but
                # EXECUTING a tool (tools/call) needs a Bearer token everywhere —
                # including cart/checkout (they are money-adjacent). Only admin
                # is gated at the transport level too.
                'required_for': ['admin', 'cart', 'checkout'],
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
    # Honest capability flags: we only genuinely *accept* verified-agent traffic
    # when the origin honors the headers (the CF-injected shared secret is set).
    accepts = _trusted_agent_enabled()
    return JsonResponse(
        {
            'name': store_slug(),
            'version': '0.1.0',
            'accepts': {
                'visa_trusted_agent': accepts,
                'mastercard_verifiable_intent': accepts,
                'cloudflare_web_bot_auth': accepts,
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
            # Omitted when the merchant has set no contact address: telling an
            # agent to mail an address that does not exist is worse than silence.
            **({'contact': store_contact_email()} if store_contact_email() else {}),
        }
    )
