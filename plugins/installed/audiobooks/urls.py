"""audiobooks — dashboard URLs (mounted at dashboard/audiobooks/ by ready())."""

from __future__ import annotations

from django.urls import path

from plugins.installed.audiobooks import dashboard_views

app_name = 'audiobooks'

urlpatterns = [
    path(
        '<uuid:audiobook_id>/generate/',
        dashboard_views.generate_audiobook_view,
        name='generate',
    ),
    path(
        '<uuid:audiobook_id>/status/',
        dashboard_views.audiobook_status_view,
        name='status',
    ),
]
