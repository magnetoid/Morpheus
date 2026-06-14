"""Dashboard routes — mounted under /dashboard/newsletter/."""

from __future__ import annotations

from django.urls import path

from plugins.installed.newsletter import dashboard

app_name = 'newsletter_dash'

urlpatterns = [
    path('', dashboard.subscribers_view, name='subscribers'),
    path('popups/', dashboard.popups_view, name='popups'),
    path('popups/<uuid:popup_id>/', dashboard.popup_edit_view, name='popup_edit'),
]
