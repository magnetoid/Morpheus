"""Shipping dashboard sub-routes (mounted under /dashboard/shipping/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.shipping import dashboard

app_name = 'shipping_dashboard'

urlpatterns = [
    path('zones/', dashboard.zones, name='zones'),
    path('rates/', dashboard.rates, name='rates'),
]
