"""Storefront nav context for book taxonomies (Genres, Topics).

Replaces the old category-driven Genres menu: genres/topics are now real
book_product models, so the nav is sourced here (book_product owns the data) —
not from catalog's `nav_categories`. Cached briefly + fail-soft: a DB hiccup or
a disabled book_product plugin yields an empty list, never a 500.
"""

from __future__ import annotations

_NAV_GENRES_CACHE_KEY = 'storefront:nav_genres:v1'
_NAV_TOPICS_CACHE_KEY = 'storefront:nav_topics:v1'
_NAV_CACHE_TTL = 300
_MAX_GENRES = 24
_MAX_TOPICS = 18


def _active_terms(model, cache_key, limit):
    from django.core.cache import cache  # noqa: PLC0415

    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    data: list[dict] = []
    try:
        from django.db.models import Count  # noqa: PLC0415

        # Most-stocked first — so the menu surfaces "Love"/"Romance", not the
        # alphabetically-first long-tail tag. Empty terms are excluded (their
        # pages would be bare).
        qs = (
            model.objects.filter(is_active=True)
            .annotate(_n=Count('books'))
            .filter(_n__gt=0)
            .order_by('-_n', 'name')[:limit]
        )
        for obj in qs:
            data.append({'name': obj.name, 'slug': obj.slug})
        cache.set(cache_key, data, _NAV_CACHE_TTL)
    except Exception:  # noqa: BLE001 — nav must never break a page render
        data = []
    return data


def nav_genres(request):
    """Active genres for the storefront mega menu (each → /genre/<slug>/)."""
    try:
        from plugins.installed.book_product.models import Genre  # noqa: PLC0415

        return {'nav_genres': _active_terms(Genre, _NAV_GENRES_CACHE_KEY, _MAX_GENRES)}
    except Exception:  # noqa: BLE001
        return {'nav_genres': []}


def nav_topics(request):
    """Active topics for the storefront mega menu (each → /topic/<slug>/)."""
    try:
        from plugins.installed.book_product.models import Topic  # noqa: PLC0415

        return {'nav_topics': _active_terms(Topic, _NAV_TOPICS_CACHE_KEY, _MAX_TOPICS)}
    except Exception:  # noqa: BLE001
        return {'nav_topics': []}
