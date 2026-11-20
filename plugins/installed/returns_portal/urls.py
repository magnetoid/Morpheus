"""The withdrawal function's pages, mounted at the site root (v0.181.0)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.returns_portal import views

app_name = 'returns_portal'

urlpatterns = [
    path('withdraw/', views.withdraw, name='withdraw'),
    path('withdraw/confirm/', views.confirm, name='withdraw_confirm'),
    path('withdraw/sent/', views.sent, name='withdraw_sent'),
]
