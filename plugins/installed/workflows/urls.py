"""URL routes for the workflows dashboard."""
from __future__ import annotations

from django.urls import path

from plugins.installed.workflows import views

app_name = 'workflows'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.workflow_form, name='create'),
    path('<uuid:workflow_id>/', views.workflow_form, name='edit'),
    path('<uuid:workflow_id>/runs/', views.runs, name='runs'),
    path('<uuid:workflow_id>/test/', views.dry_run_view, name='test'),
    path('<uuid:workflow_id>/delete/', views.delete, name='delete'),
]
