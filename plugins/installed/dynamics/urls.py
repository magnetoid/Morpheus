"""dynamics dashboard routes (mounted under /dashboard/dynamics/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = 'dynamics'

urlpatterns = [
    path('', views.index, name='index'),
    path('proposals/', views.proposals, name='proposals'),
    path('proposals/<uuid:proposal_id>/', views.proposal_action, name='proposal_action'),
    path('new/', views.edit_block, {'block_id': None}, name='block_new'),
    path('<uuid:block_id>/', views.edit_block, name='block_edit'),
    path('<uuid:block_id>/delete/', views.delete_block, name='block_delete'),
]
