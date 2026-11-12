"""Payments' dashboard routes (mounted under /dashboard/payments/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.payments import views_dashboard

app_name = 'payments_dashboard'

urlpatterns = [
    path('capture/<str:order_number>/', views_dashboard.capture, name='capture'),
]
