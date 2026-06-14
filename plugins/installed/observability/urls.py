"""Observability dashboard routes (mounted under /dashboard/observability/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.observability import views

app_name = 'observability'

urlpatterns = [
    path('audit/', views.audit_log_view, name='audit_log'),
]
