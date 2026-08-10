"""Storefront routes owned by lookbook (mounted at site root by
``register_urls``). Present only while the plugin is enabled — disabling it
404s every route below (modular-os disable test)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.lookbook import views

app_name = 'lookbook'

urlpatterns = [
    path('looks/<slug:slug>/', views.look_detail, name='look_detail'),
]
