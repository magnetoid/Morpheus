from __future__ import annotations

from django.urls import path

from plugins.installed.affiliates import views

app_name = 'affiliates'

urlpatterns = [
    path('r/<str:code>', views.affiliate_redirect, name='redirect'),
    # Customer self-service flow
    path('affiliates/apply/', views.apply, name='apply'),
    path('affiliates/me/', views.dashboard, name='dashboard'),
    path('affiliates/me/links/new/', views.create_link, name='create_link'),
]
