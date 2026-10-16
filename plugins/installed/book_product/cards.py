"""What a storefront book card shows from the book: genre, author, formats.

Answers PRODUCT_CARD_META, read by core's `{% product_card_meta %}` on every grid
that renders a book card. A listing that prefetches `book`, `book__genres` and
`variants` (the all-books page does, through LISTING_FACETS) costs no query
here; any other product — an ORM row without those, or a GraphQL dict — is
looked up once and cached for ten minutes.
"""

from __future__ import annotations

import contextlib

CACHE_TTL = 600
_LABELS = {'print': 'Print', 'digital': 'PDF', 'audiobook': 'Audiobook'}


def _formats(variants) -> list[str]:
    """Card labels for a book's active formats, in Print, PDF, Audiobook order."""
    kinds = set()
    for v in variants:
        if not getattr(v, 'is_active', True):
            continue
        name = (v.name or '').lower()
        if v.variant_type == 'audiobook' or 'audio' in name:
            kinds.add('audiobook')
        elif v.variant_type == 'digital':
            kinds.add('digital')
        else:
            kinds.add('print')
    if not kinds:
        kinds.add('print')  # a book with no variants is a printed book
    return [_LABELS[k] for k in ('print', 'digital', 'audiobook') if k in kinds]


def meta_from(product) -> dict:
    """The card's book data from an ORM product (prefetched relations when present)."""
    try:
        book = product.book
    except Exception:  # noqa: BLE001 — RelatedObjectDoesNotExist: not a book
        return {}
    if book is None:
        return {}
    genres = sorted(
        (g for g in book.genres.all() if g.is_active), key=lambda g: (g.sort_order, g.name)
    )
    formats = _formats(product.variants.all())
    return {
        'genre': genres[0].name if genres else '',
        'author': book.author or '',
        'formats': formats,
        # Shown only when it says something: a print-only book needs no line.
        'formats_line': ' · '.join(formats) if formats != ['Print'] else '',
    }


def _prefetched(product) -> bool:
    cache = getattr(product, '_prefetched_objects_cache', None) or {}
    fields = getattr(getattr(product, '_state', None), 'fields_cache', {}) or {}
    return 'variants' in cache and 'book' in fields


def card_meta(product) -> dict:
    """Genre, author and formats for a book card; {} for anything that isn't a book."""
    if product is None:
        return {}
    if hasattr(product, '_state') and _prefetched(product):
        return meta_from(product)
    pid = getattr(product, 'pk', None) or (product.get('id') if isinstance(product, dict) else None)
    if not pid:
        return {}
    from django.core.cache import cache

    from plugins.installed.catalog.models import Product

    key = f'book_card:v1:{pid}'
    try:
        hit = cache.get(key)
    except Exception:  # noqa: BLE001 — a cache outage never breaks a grid
        hit = None
    if hit is not None:
        return hit
    row = (
        Product.objects.select_related('book')
        .prefetch_related('book__genres', 'variants')
        .filter(pk=pid)
        .first()
    )
    meta = meta_from(row) if row is not None else {}
    with contextlib.suppress(Exception):  # a cache outage never breaks a grid
        cache.set(key, meta, CACHE_TTL)
    return meta
