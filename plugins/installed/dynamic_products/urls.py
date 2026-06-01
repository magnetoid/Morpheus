"""dynamic_products dashboard routes (mounted under /dashboard/dynamic-products/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = 'dynamic_products'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.edit_block, {'block_id': None}, name='block_new'),
    path('<uuid:block_id>/', views.edit_block, name='block_edit'),
    path('<uuid:block_id>/delete/', views.delete_block, name='block_delete'),
]
