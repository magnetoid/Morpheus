"""Affiliates dashboard sub-routes (mounted under /dashboard/affiliates/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.affiliates import dashboard

app_name = 'affiliates_dashboard'

urlpatterns = [
    path('affiliates/<uuid:affiliate_id>/', dashboard.affiliate_detail, name='affiliate_detail'),
    path('programs/new/', dashboard.program_detail, {'program_id': None}, name='program_new'),
    path('programs/<uuid:program_id>/', dashboard.program_detail, name='program_detail'),
]
