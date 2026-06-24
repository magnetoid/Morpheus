"""URL route for the /.well-known/acp.json ACP discovery manifest."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agentic_checkout import well_known

app_name = 'agentic_checkout_well_known'

urlpatterns = [
    path('acp.json', well_known.acp_manifest, name='acp'),
]
