"""Root-mounted PWA routes (mounted with prefix='')."""
from __future__ import annotations

from django.urls import path

from plugins.installed.pwa import views

app_name = 'pwa'

urlpatterns = [
    path('manifest.webmanifest', views.manifest, name='manifest'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline, name='offline'),
]
