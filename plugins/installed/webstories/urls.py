"""Webstories URLs — mounted at the storefront root via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.webstories import views

app_name = 'webstories'

urlpatterns = [
    path('story/<slug:slug>/', views.story_page, name='story'),
]
