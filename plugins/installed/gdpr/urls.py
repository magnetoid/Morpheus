"""GDPR data-rights URLs — mounted at the site root via register_urls."""

from __future__ import annotations

from django.urls import path

from plugins.installed.gdpr import views

app_name = 'gdpr'

urlpatterns = [
    path('account/privacy/', views.account_privacy, name='account_privacy'),
    path('account/data-export/', views.account_data_export, name='account_data_export'),
    path('account/delete/', views.account_delete, name='account_delete'),
]
