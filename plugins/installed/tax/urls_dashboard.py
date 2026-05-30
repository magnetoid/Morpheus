"""Tax dashboard sub-routes (mounted under /dashboard/tax/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.tax import dashboard

app_name = 'tax_dashboard'

urlpatterns = [
    path('regions/', dashboard.regions, name='regions'),
    path('rates/', dashboard.rates, name='rates'),
]
