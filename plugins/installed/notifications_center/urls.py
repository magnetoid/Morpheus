"""URL routes for the notifications center."""

from __future__ import annotations

from django.urls import path

from plugins.installed.notifications_center import views

app_name = 'notifications_center'

urlpatterns = [
    path('', views.notifications_list, name='list'),
    path('<uuid:notification_id>/read/', views.mark_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    # JSON API used by the topbar bell dropdown.
    path('api/latest/', views.api_latest, name='api_latest'),
]
