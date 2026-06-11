"""HTTP API routes mounted under `/api/`."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agent_core import views

app_name = 'agent_core_api'

urlpatterns = [
    path('agents/', views.list_agents_view, name='list_agents'),
    path('agents/<str:agent_name>/invoke', views.invoke_agent_view, name='invoke_agent'),
    path('agents/<str:agent_name>/stream', views.stream_agent_view, name='stream_agent'),
]
