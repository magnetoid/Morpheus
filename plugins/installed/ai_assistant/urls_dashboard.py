"""Dashboard routes owned by ai_assistant (mounted at /dashboard/pulse/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.ai_assistant.views import pulse

app_name = 'ai_assistant_dashboard'

urlpatterns = [
    path('refresh/', pulse.pulse_refresh, name='pulse_refresh'),
    path('<uuid:insight_id>/dismiss/', pulse.pulse_dismiss, name='pulse_dismiss'),
]
