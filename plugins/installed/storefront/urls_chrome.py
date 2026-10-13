"""Storefront machine endpoints: never language-prefixed (surface='chrome')."""

from __future__ import annotations

from django.urls import path

from plugins.installed.storefront.views.csrf import csrf_token_view

app_name = 'storefront_chrome'

urlpatterns = [
    path('csrf/', csrf_token_view, name='csrf'),
]
