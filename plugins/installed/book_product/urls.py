"""Storefront facet routes for book attributes (mounted at root)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.book_product import views

app_name = 'book_product'

urlpatterns = [
    path('publisher/<slug:slug>/', views.publisher_detail, name='publisher'),
    path('series/<slug:slug>/', views.series_detail, name='series'),
    path('imprint/<slug:slug>/', views.imprint_detail, name='imprint'),
    path('format/<slug:value>/', views.format_detail, name='format'),
    path('language/<slug:value>/', views.language_detail, name='language'),
]
