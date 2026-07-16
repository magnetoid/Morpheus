"""Dashboard routes for Book taxonomies (mounted under /dashboard/book-taxonomies/)."""

from __future__ import annotations

from django.urls import path

from plugins.installed.book_product import dashboard_taxonomies as views

app_name = 'book_product_dashboard'

urlpatterns = [
    path('', views.taxonomies_list, name='taxonomies'),
    # Curated taxonomies (Genre, Topic) — add/edit/delete (prefixed to avoid
    # clashing with the auto-discovered <taxonomy>/<slug>/ routes below).
    path('curated/<slug:kind>/new/', views.curated_add, name='curated_add'),
    path('curated/<slug:kind>/backfill/', views.curated_backfill, name='curated_backfill'),
    path('curated/<slug:kind>/<slug:slug>/edit/', views.curated_edit, name='curated_edit'),
    path('curated/<slug:kind>/<slug:slug>/delete/', views.curated_delete, name='curated_delete'),
    path('<slug:taxonomy>/landing/', views.taxonomy_root_edit, name='taxonomy_root_edit'),
    path('<slug:taxonomy>/generate/', views.taxonomy_generate, name='taxonomy_root_generate'),
    path('<slug:taxonomy>/<slug:slug>/edit/', views.taxonomy_edit, name='taxonomy_edit'),
    path(
        '<slug:taxonomy>/<slug:slug>/generate/', views.taxonomy_generate, name='taxonomy_generate'
    ),
]
