"""URL routes for /.well-known/ agent-discovery files."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agent_mcp import well_known

app_name = 'agent_mcp_well_known'

urlpatterns = [
    # The business profile the UCP specification describes (2026-08-25).
    path('ucp', well_known.ucp_profile, name='ucp_profile'),
    # The pre-spec manifest (v0.30.0); kept for the clients that learned it.
    path('ucp.json', well_known.ucp_manifest, name='ucp'),
    path('agent.json', well_known.trusted_agent_manifest, name='agent'),
]
