"""Flipbook URLs — mounted at the storefront root via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.flipbook import views

app_name = 'flipbook'

urlpatterns = [
    path('p/<slug:slug>/flipbook/', views.flipbook, name='flipbook'),
]
