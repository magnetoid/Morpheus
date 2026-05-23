"""Cloudflare admin URLs — mounted at /dashboard/cloudflare/ via register_urls."""
from __future__ import annotations

from django.urls import path

from plugins.installed.cloudflare import views

app_name = 'cloudflare'

urlpatterns = [
    path('', views.overview, name='overview'),
    path('accounts/<uuid:account_id>/sync/', views.account_sync, name='account_sync'),
    path('zones/', views.zones_list, name='zones'),
    path('zones/<uuid:zone_id>/', views.zone_detail, name='zone_detail'),
    path('zones/<uuid:zone_id>/purge/', views.purge_form, name='purge'),
    path('zones/<uuid:zone_id>/analytics/', views.analytics, name='analytics'),
    path('log/', views.invalidations_log, name='log'),
]
