"""Listing editor routes under /dashboard/listings/ (the list is a DashboardPage)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.booking_marketplace import dashboard_listings as views

app_name = 'booking_marketplace_dash'

urlpatterns = [
    path('new/', views.listing_new, name='listing_new'),
    path('<uuid:pk>/edit/', views.listing_edit, name='listing_edit'),
]
