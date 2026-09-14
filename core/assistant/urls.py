"""Assistant URL routes — mounted at `/dashboard/assistant/` in the project URLconf."""

from __future__ import annotations

from django.urls import path

from core.assistant import views, views_proposals

app_name = 'assistant'

urlpatterns = [
    path('', views.assistant_page, name='page'),
    path('stream/', views.assistant_stream, name='stream'),
    path('history/', views.assistant_history, name='history'),
    path('page-help/', views.assistant_page_help, name='page_help'),
    # Staged-changes inbox (staff, staged-changes design §3).
    path('proposals/', views_proposals.proposals_page, name='proposals'),
    # Ops-proposal inbox actions (staff, staged-changes design §3).
    path(
        'proposals/ops/<uuid:proposal_id>/action/',
        views_proposals.ops_proposal_action,
        name='ops_proposal_action',
    ),
]
