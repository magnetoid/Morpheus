from __future__ import annotations

from django.urls import path

from plugins.installed.affiliates import views

app_name = 'affiliates'

urlpatterns = [
    path('r/<str:code>', views.affiliate_redirect, name='redirect'),
    # Customer self-service flow
    path('affiliates/apply/', views.apply, name='apply'),
    path('affiliates/me/', views.dashboard, name='dashboard'),
    path('affiliates/me/links/', views.links, name='links'),
    path('affiliates/me/links/new/', views.create_link, name='create_link'),
    path('affiliates/me/links/<uuid:link_id>/edit/', views.edit_link, name='edit_link'),
    path('affiliates/me/conversions/', views.conversions, name='conversions'),
    path('affiliates/me/payouts/', views.payouts, name='payouts'),
    path('affiliates/me/settings/', views.settings, name='settings'),
]
