"""URLconfs for agent_core. Mounted twice: under `api/` for HTTP API and
under `dashboard/agents/` for the merchant console."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agent_core import views

app_name = 'agent_core'

api_urlpatterns = [
    path('agents/', views.list_agents_view, name='list_agents'),
    path('agents/<str:agent_name>/invoke', views.invoke_agent_view, name='invoke_agent'),
    path('agents/<str:agent_name>/stream', views.stream_agent_view, name='stream_agent'),
]

dashboard_urlpatterns = [
    path('', views.runs_dashboard_view, name='runs'),
    path('console/', views.merchant_ops_chat_view, name='console'),
    path('<uuid:run_id>/', views.run_detail_view, name='run_detail'),
]
