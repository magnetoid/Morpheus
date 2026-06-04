"""Storefront context processors for the catalog plugin."""

from __future__ import annotations

_NAV_CACHE_KEY = 'storefront:nav_categories:v1'
_NAV_AUTHORS_CACHE_KEY = 'storefront:nav_authors:v1'
_NAV_BOOKS_CACHE_KEY = 'storefront:nav_featured_books:v1'
_NAV_CACHE_TTL = 300
_MAX_CHILDREN = 8
_MAX_AUTHORS = 30
_MAX_NAV_BOOKS = 8


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


def nav_authors(request):
    """Distinct book authors for the storefront Authors mega menu.

    Reads the BookProduct model first, falling back to legacy `book.author`
    metafields (book_product.compat) — each links to /author/<slugify(name)>/,
    which author_detail resolves the same way. Cached + fail-soft.
    """
    from django.core.cache import cache  # noqa: PLC0415

    cached = cache.get(_NAV_AUTHORS_CACHE_KEY)
    if cached is not None:
        return {'nav_authors': cached}

    data: list[dict] = []
    try:
        from django.utils.text import slugify  # noqa: PLC0415

        from plugins.installed.book_product.compat import distinct_values  # noqa: PLC0415

        for name in distinct_values('author')[:_MAX_AUTHORS]:
            data.append({'name': name, 'slug': slugify(name)})
        cache.set(_NAV_AUTHORS_CACHE_KEY, data, _NAV_CACHE_TTL)
    except Exception:  # noqa: BLE001
        data = []
    return {'nav_authors': data}


def _cover_url(image_row) -> str:
    """Prefer the WebP variant (smaller) for a ProductImage; '' when absent."""
    if getattr(image_row, 'webp_image', None) and image_row.webp_image.name:
        return image_row.webp_image.url
    if getattr(image_row, 'image', None) and image_row.image.name:
        return image_row.image.url
    return ''


def nav_featured_books(request):
    """A handful of book covers for the mega menu — featured first, then recent.

    Only active products that actually have a cover image are included (a
    coverless tile is worse than fewer tiles). Cached + fail-soft.
    """
    from django.core.cache import cache  # noqa: PLC0415

    cached = cache.get(_NAV_BOOKS_CACHE_KEY)
    if cached is not None:
        return {'nav_featured_books': cached}

    data: list[dict] = []
    try:
        from plugins.installed.catalog.models import Product  # noqa: PLC0415

        seen: set = set()
        qs = (
            Product.objects.filter(status='active')
            .order_by('-is_featured', '-created_at')
            .prefetch_related('images')[: _MAX_NAV_BOOKS * 4]
        )
        for p in qs:
            cover = _cover_url(p.primary_image)
            if not cover or p.id in seen:
                continue
            seen.add(p.id)
            data.append({'name': p.name, 'slug': p.slug, 'image': cover})
            if len(data) >= _MAX_NAV_BOOKS:
                break
        cache.set(_NAV_BOOKS_CACHE_KEY, data, _NAV_CACHE_TTL)
    except Exception:  # noqa: BLE001 — nav must never break a page render
        data = []
    return {'nav_featured_books': data}
