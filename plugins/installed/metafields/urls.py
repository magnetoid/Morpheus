"""URL routes for the metafields dashboard."""
from __future__ import annotations

from django.urls import path

from plugins.installed.metafields import views

app_name = 'metafields'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.create_form, name='create'),
    path('<uuid:metafield_id>/edit/', views.edit_form, name='edit'),
    path('<uuid:metafield_id>/delete/', views.delete, name='delete'),
    # JSON API used by the inline editor partial — read + write per record.
    path('api/list/', views.api_list, name='api_list'),
    path('api/set/', views.api_set, name='api_set'),
    path('api/delete/', views.api_delete, name='api_delete'),
]
