from __future__ import annotations

from django.urls import path

from plugins.installed.marketplace import views

app_name = 'marketplace'

urlpatterns = [
    # Storefront vendor self-service flow.
    path('vendor/apply/', views.apply, name='apply'),
    path('vendor/me/', views.dashboard, name='dashboard'),
]
