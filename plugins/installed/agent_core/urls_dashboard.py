"""Admin dashboard routes mounted under `/dashboard/agents/`."""

from __future__ import annotations

from django.urls import path

from plugins.installed.agent_core import views

app_name = 'agent_core_dash'

urlpatterns = [
    path('', views.runs_dashboard_view, name='runs'),
    path('console/', views.merchant_ops_chat_view, name='console'),
    path('observability/', views.observability_view, name='observability'),
    path('background/', views.background_agents_view, name='background'),
    path(
        'background/<uuid:bg_id>/<str:action>/',
        views.background_agent_action_view,
        name='background_action',
    ),
    # Self-development approval dashboard (Linda's draft→apply loop).
    # Linda memory editor (owner curates Linda's cross-session facts).
    path('memory/', views.memory_list_view, name='memory'),
    path('memory/action/', views.memory_action_view, name='memory_action'),
    path('<uuid:run_id>/', views.run_detail_view, name='run_detail'),
]
