"""Storefront context processors for the catalog plugin."""

from __future__ import annotations

_NAV_CACHE_KEY = 'storefront:nav_categories:v1'
_NAV_CACHE_TTL = 300
_MAX_CHILDREN = 8


def nav_categories(request):
    """Top-level active categories (+ their active children) for the storefront
    Genres mega menu.

    Cached briefly and fail-soft: a DB hiccup or a disabled catalog plugin
    yields an empty list, never a 500. Invalidated naturally by the TTL — the
    nav doesn't need to be instantly consistent with category edits.
    """
    from django.core.cache import cache  # noqa: PLC0415

    cached = cache.get(_NAV_CACHE_KEY)
    if cached is not None:
        return {'nav_categories': cached}

    data: list[dict] = []
    try:
        from django.db.models import Prefetch  # noqa: PLC0415

        from plugins.installed.catalog.models import Category  # noqa: PLC0415

        active_children = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
        roots = (
            Category.objects.filter(parent__isnull=True, is_active=True)
            .order_by('sort_order', 'name')
            .prefetch_related(Prefetch('children', queryset=active_children))
        )
        for root in roots:
            children = list(root.children.all())[:_MAX_CHILDREN]
            data.append(
                {
                    'name': root.name,
                    'slug': root.slug,
                    'children': [{'name': c.name, 'slug': c.slug} for c in children],
                }
            )
        cache.set(_NAV_CACHE_KEY, data, _NAV_CACHE_TTL)
    except Exception:  # noqa: BLE001 — nav must never break a page render
        data = []
    return {'nav_categories': data}
