"""URL routes for the media library."""
from __future__ import annotations

from django.urls import path

from plugins.installed.media import views

app_name = 'media'

urlpatterns = [
    path('', views.library, name='library'),
    path('upload/', views.upload, name='upload'),
    path('<uuid:asset_id>/delete/', views.delete, name='delete'),
    path('<uuid:asset_id>/edit/', views.edit_meta, name='edit_meta'),
    path('picker/', views.picker_modal, name='picker'),
    path('api/upload/', views.api_upload, name='api_upload'),
]
