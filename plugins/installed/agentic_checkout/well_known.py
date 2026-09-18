"""ACP discovery manifest — served from /.well-known/acp.json.

Mirrors ``agent_mcp/well_known.py`` (which serves ``ucp.json`` + ``agent.json``).
Advertises the protocol version we implement, the checkout base URL, the
product-feed URL, supported payment handlers (Stripe Shared Payment Token), and
the Bearer ``auth`` registration. An ACP agent reads this to learn how to
discover the catalog and create a checkout session.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from core.utils.site import store_name, store_slug
from plugins.installed.agentic_checkout.app import ACP_API_VERSION
from plugins.installed.agentic_checkout.auth import ACP_SCOPE


@require_http_methods(['GET'])
def acp_manifest(request: HttpRequest) -> JsonResponse:
    base = request.build_absolute_uri('/').rstrip('/')
    return JsonResponse(
        {
            'protocolVersion': ACP_API_VERSION,
            'name': store_slug('acp'),
            'description': f'Agentic Commerce Protocol — {store_name()} storefront.',
            'checkout': {
                'base_url': f'{base}/acp/checkout_sessions',
                'operations': [
                    'createCheckoutSession',
                    'getCheckoutSession',
                    'updateCheckoutSession',
                    'cancelCheckoutSession',
                    'completeCheckoutSession',
                ],
            },
            'feed': {
                'url': f'{base}/acp/feed.json',
            },
            'capabilities': {
                'payment_handlers': ['stripe_shared_payment_token'],
                'currencies_minor_units': True,
            },
            'auth': {
                'type': 'bearer',
                'scopes': [ACP_SCOPE, 'catalog.read'],
                'registration_url': f'{base}/dashboard/apps/agent_mcp/tokens/',
            },
        }
    )
