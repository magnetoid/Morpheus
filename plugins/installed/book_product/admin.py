"""Django-admin CRUD for the curated book taxonomies (Genre, Topic).

Genres are seeded by the categories→genres migration; Topics start empty and are
curated here. (A first-class dashboard editor can follow; admin covers CRUD now.)
"""

from __future__ import annotations

from django.contrib import admin

from plugins.installed.book_product.models import Genre, Topic


class _CuratedAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(Genre)
class GenreAdmin(_CuratedAdmin):
    pass


@admin.register(Topic)
class TopicAdmin(_CuratedAdmin):
    pass
