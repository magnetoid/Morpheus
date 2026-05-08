"""URL routes for the MCP server.

Mounted at /mcp/ by the plugin loader:
  POST /mcp/v1/        — JSON-RPC 2.0 endpoint (initialize, tools/list,
                         tools/call, resources/list)
  GET  /mcp/v1/health/ — liveness probe
  GET  /.well-known/ai-plugin.json (mounted in `urls_well_known`) for
       discovery by ChatGPT-style plugin clients.
"""
from __future__ import annotations

from django.urls import path

from plugins.installed.agent_mcp import views

app_name = 'agent_mcp'

urlpatterns = [
    path('v1/', views.rpc_endpoint, name='rpc'),
    path('v1/health/', views.health, name='health'),
    path('v1/manifest.json', views.manifest, name='manifest'),
]
