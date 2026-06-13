"""Dashboard routes for Book taxonomies (mounted under /dashboard/book-taxonomies/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.book_product import dashboard_taxonomies as views

app_name = 'book_product_dashboard'

urlpatterns = [
    path('', views.taxonomies_list, name='taxonomies'),
    path('<slug:taxonomy>/landing/', views.taxonomy_root_edit, name='taxonomy_root_edit'),
    path('<slug:taxonomy>/generate/', views.taxonomy_generate, name='taxonomy_root_generate'),
    path('<slug:taxonomy>/<slug:slug>/edit/', views.taxonomy_edit, name='taxonomy_edit'),
    path(
        '<slug:taxonomy>/<slug:slug>/generate/', views.taxonomy_generate, name='taxonomy_generate'
    ),
]
