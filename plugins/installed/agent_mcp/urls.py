"""URL routes for the MCP cluster.

Mounted at /mcp/ by the plugin loader:

  Legacy single-server (backward compatible with the existing
  Claude Desktop / Cursor integrations):
    POST /mcp/v1/                JSON-RPC 2.0
    GET  /mcp/v1/health/         liveness probe
    GET  /mcp/v1/manifest.json   ChatGPT-style plugin manifest

  Shopify-shaped cluster (per-audience servers):
    POST /mcp/storefront/v1/     public catalog reads (no auth)
    POST /mcp/cart/v1/           cart operations (no auth)
    POST /mcp/checkout/v1/       checkout operations (no auth)
    POST /mcp/admin/v1/          Linda's full tool catalog (Bearer auth)

External discovery files live under /.well-known/ (mounted in
``plugins.installed.agent_mcp.urls_well_known``).
"""
from __future__ import annotations

from django.urls import path

from plugins.installed.agent_mcp import servers, views

app_name = 'agent_mcp'

urlpatterns = [
    # Legacy server — kept stable for existing integrations.
    path('v1/', views.rpc_endpoint, name='rpc'),
    path('v1/health/', views.health, name='health'),
    path('v1/manifest.json', views.manifest, name='manifest'),

    # Cluster servers.
    path('storefront/v1/', servers.storefront_endpoint, name='storefront_rpc'),
    path('cart/v1/',       servers.cart_endpoint,       name='cart_rpc'),
    path('checkout/v1/',   servers.checkout_endpoint,   name='checkout_rpc'),
    path('admin/v1/',      servers.admin_endpoint,      name='admin_rpc'),
]
