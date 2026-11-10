"""Inventory dashboard routes (mounted under /dashboard/inventory/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.inventory import dashboard

app_name = 'inventory_dashboard'

urlpatterns = [
    path('warehouses/', dashboard.warehouses, name='warehouses'),
]
