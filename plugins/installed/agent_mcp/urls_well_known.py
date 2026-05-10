"""URL routes for /.well-known/ agent-discovery files."""
from __future__ import annotations

from django.urls import path

from plugins.installed.agent_mcp import well_known

app_name = 'agent_mcp_well_known'

urlpatterns = [
    path('ucp.json',   well_known.ucp_manifest,            name='ucp'),
    path('agent.json', well_known.trusted_agent_manifest,  name='agent'),
]
