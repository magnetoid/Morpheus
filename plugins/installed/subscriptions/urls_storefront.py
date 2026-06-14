"""Public storefront routes — the membership / plans page + subscribe."""

from __future__ import annotations

from django.urls import path

from plugins.installed.subscriptions import views_storefront as v

app_name = 'subscriptions_storefront'

urlpatterns = [
    path('membership/', v.membership_view, name='membership'),
    path('membership/subscribe/', v.subscribe_view, name='subscribe'),
]
