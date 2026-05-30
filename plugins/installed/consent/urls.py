"""Consent URLs — mounted at /consent/ via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.consent import views

app_name = 'consent'

urlpatterns = [
    path('save/', views.save, name='save'),
    path('preferences/', views.preferences, name='preferences'),
]
