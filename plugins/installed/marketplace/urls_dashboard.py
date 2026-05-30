"""Marketplace dashboard sub-routes (mounted under /dashboard/marketplace/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.marketplace import dashboard

app_name = 'marketplace_dashboard'

urlpatterns = [
    path('vendors/<uuid:vendor_id>/', dashboard.vendor_detail, name='vendor_detail'),
]
