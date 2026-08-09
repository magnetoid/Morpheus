"""MCP cluster — per-audience tool whitelists.

The legacy `/mcp/v1/` endpoint stays as the "curated public reads"
alias (backward-compatible). This module adds four focused servers
that mirror Shopify's shape:

  /mcp/storefront/v1/   — catalog reads
  /mcp/cart/v1/         — same, plus cart manipulation
  /mcp/checkout/v1/     — same, plus checkout (build + quote; not the charge)
  /mcp/admin/v1/        — Linda's admin tool catalog

Auth contract: `initialize` and `tools/list` are anonymously reachable on
every cluster (so a client can discover the surface), but EXECUTING any tool
(`tools/call`) requires a valid Bearer token — the dispatcher rejects an
unauthenticated `tools/call` (see ``_handle_tools_call`` in views.py). The
cluster wrappers set ``require_auth=False`` only to allow that anonymous
discovery, NOT to allow anonymous execution.

Each view sets a thread-local "active cluster" before delegating to
the existing ``rpc_endpoint`` dispatcher, then unsets it. The
dispatcher's ``_public_tools()`` honours the active cluster's
whitelist for that request.
"""

from __future__ import annotations

import threading

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Per-server tool whitelists. Add a tool to a server here to expose it.
STOREFRONT_TOOLS = {
    'products.search',
    'products.get',
    'cms.pages',
    'analytics.top_products',
    'memory.recall',
}

# Cart / checkout add the buyer-agent build+quote tools on top of the
# storefront reads. These tool bodies live in the agentic_checkout plugin
# (which owns the cart-session model); when it is disabled they simply don't
# resolve, so the clusters fall back to storefront-only and the UCP manifest's
# cart/checkout capability reports false. COMPLETION is intentionally absent —
# the charge stays on the /acp/ REST endpoint behind payments_enabled.
CART_TOOLS = STOREFRONT_TOOLS | {'cart.create', 'cart.add_item', 'cart.get'}
CHECKOUT_TOOLS = CART_TOOLS | {'checkout.get_session', 'checkout.set_buyer'}

# Admin: no whitelist → all tools (Linda's full catalog).
ADMIN_NAMES: set[str] | None = None


_state = threading.local()


def _set_cluster(label: str, names: set[str] | None) -> None:
    _state.cluster = {'label': label, 'names': names}


def _clear_cluster() -> None:
    _state.cluster = None


def active_cluster() -> dict | None:
    """Public read accessor used by ``views._public_tools``.
    Returns the active cluster's whitelist + label, or None when the
    legacy ``/mcp/v1/`` endpoint is serving the request.
    """
    return getattr(_state, 'cluster', None)


def _make_endpoint(names: set[str] | None, label: str, require_auth: bool):
    """Build a Django view that runs the standard MCP dispatcher with a
    cluster-scoped tool whitelist."""
    from plugins.installed.agent_mcp import views as base_views

    @csrf_exempt
    @require_http_methods(['POST'])
    def view(request: HttpRequest) -> HttpResponse:
        _set_cluster(label, names)
        try:
            if require_auth and not base_views._is_authed(request):
                return JsonResponse(
                    base_views._error_envelope(
                        None,
                        base_views._E_AUTH,
                        f'authentication required for {label} server',
                    ),
                    status=401,
                )
            return base_views.rpc_endpoint(request)
        finally:
            _clear_cluster()

    view.__name__ = f'mcp_{label}_endpoint'
    view.__qualname__ = view.__name__
    return view


storefront_endpoint = _make_endpoint(STOREFRONT_TOOLS, 'storefront', False)
cart_endpoint = _make_endpoint(CART_TOOLS, 'cart', False)
checkout_endpoint = _make_endpoint(CHECKOUT_TOOLS, 'checkout', False)
admin_endpoint = _make_endpoint(ADMIN_NAMES, 'admin', True)
