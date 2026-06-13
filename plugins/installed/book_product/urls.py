"""Storefront facet routes for book attributes (mounted at root)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.book_product import views

app_name = 'book_product'

urlpatterns = [
    # Taxonomy root listing pages — one index per kind (author lives in the
    # storefront app at /author/<slug>/, so its index is /authors/ here).
    path('authors/', views.authors_root, name='authors'),
    path('publishers/', views.publishers_root, name='publishers'),
    path('series/', views.series_root, name='series_index'),
    path('imprints/', views.imprints_root, name='imprints'),
    path('publisher/<slug:slug>/', views.publisher_detail, name='publisher'),
    path('series/<slug:slug>/', views.series_detail, name='series'),
    path('imprint/<slug:slug>/', views.imprint_detail, name='imprint'),
    path('format/<slug:value>/', views.format_detail, name='format'),
    path('language/<slug:value>/', views.language_detail, name='language'),
]
