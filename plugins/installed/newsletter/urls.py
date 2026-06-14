"""Public newsletter routes — mounted at /newsletter/."""

from __future__ import annotations

from django.urls import path

from plugins.installed.newsletter import views

app_name = 'newsletter'

urlpatterns = [
    path('newsletter/subscribe/', views.subscribe_view, name='subscribe'),
    path('newsletter/confirm/<str:token>/', views.confirm_view, name='confirm'),
    path('newsletter/unsubscribe/<str:token>/', views.unsubscribe_view, name='unsubscribe'),
]
