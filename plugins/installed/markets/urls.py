"""URL routes for the markets dashboard."""
from __future__ import annotations

from django.urls import path

from plugins.installed.markets import views

app_name = 'markets'

urlpatterns = [
    path('', views.index, name='index'),
    path('new/', views.market_form, name='create'),
    path('<uuid:market_id>/', views.market_form, name='edit'),
    path('<uuid:market_id>/delete/', views.market_delete, name='delete'),
]
