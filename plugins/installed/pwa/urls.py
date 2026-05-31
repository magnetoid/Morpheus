"""Root-mounted PWA routes (mounted with prefix='')."""

from __future__ import annotations

from django.urls import path

from plugins.installed.pwa import views

app_name = 'pwa'

urlpatterns = [
    path('manifest.webmanifest', views.manifest, name='manifest'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('offline/', views.offline, name='offline'),
    # Web Push opt-in (sprint #18). All under /api/push/ so existing
    # CSRF + middleware behaviours align with the rest of the JSON API.
    path('api/push/config', views.push_config, name='push_config'),
    path('api/push/subscribe', views.push_subscribe, name='push_subscribe'),
    path('api/push/unsubscribe', views.push_unsubscribe, name='push_unsubscribe'),
]
