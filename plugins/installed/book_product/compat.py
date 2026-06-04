"""Read book attributes model-first, legacy-metafield-fallback.

The BookProduct model is the source of truth for book attributes; these helpers
let storefront/catalog read it while legacy ``book.*`` metafields (seed data,
Gutenberg imports, not-yet-backfilled rows) still resolve via a fallback. Once
the remaining metafield readers (SEO jsonld/sitemaps/feeds, search backends,
webstories) + writers move to the model, the fallback — and the metafields —
can be dropped. All helpers are fail-soft (return empty on any error).
"""
# Fail-soft helpers — a missing plugin / DB hiccup must never break a render.
# ruff: noqa: S110

from __future__ import annotations

from django.utils.text import slugify


def _product_ct():
    from django.contrib.contenttypes.models import ContentType  # noqa: PLC0415

    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    return ContentType.objects.get_for_model(Product)


def distinct_values(field: str) -> list[str]:
    """Distinct non-empty values of a book `field` — model ∪ legacy metafields."""
    values: set[str] = set()
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        values.update(
            v.strip()
            for v in BookProduct.objects.exclude(**{field: ''}).values_list(field, flat=True)
            if v and str(v).strip()
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        values.update(
            v.strip()
            for v in Metafield.objects.filter(
                content_type=_product_ct(), namespace='book', key=field
            )
            .exclude(value='')
            .values_list('value', flat=True)
            if v and v.strip()
        )
    except Exception:  # noqa: BLE001
        pass
    return sorted(values, key=str.lower)


def product_ids_for(field: str, value: str) -> list[str]:
    """Product ids whose book `field` == `value` (case-insensitive) — model ∪ metafields."""
    ids: set[str] = set()
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        ids.update(
            str(pid)
            for pid in BookProduct.objects.filter(**{f'{field}__iexact': value}).values_list(
                'product_id', flat=True
            )
        )
    except Exception:  # noqa: BLE001
        pass
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        ids.update(
            str(oid)
            for oid in Metafield.objects.filter(
                content_type=_product_ct(), namespace='book', key=field, value__iexact=value
            ).values_list('object_id', flat=True)
        )
    except Exception:  # noqa: BLE001
        pass
    return list(ids)


def book_attrs(product) -> dict:
    """A product's book attributes as a flat ``{key: value}`` dict with bare
    keys ('author', 'publisher', 'pages', 'format', 'language',
    'published_year', …), model-first with legacy book.* metafield fallback.
    Drop-in for readers that consumed the raw ``book.*`` metafield dict.
    """
    out: dict = {}
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        book = BookProduct.objects.filter(product=product).first()
    except Exception:  # noqa: BLE001
        book = None
    if book is not None:
        for key, val in (
            ('author', book.author),
            ('subtitle', book.subtitle),
            ('publisher', book.publisher),
            ('imprint', book.imprint),
            ('synopsis', book.synopsis),
            ('language', book.language),
            ('series', book.series),
            ('edition', book.edition),
            ('binding', book.binding),
        ):
            if val:
                out[key] = val
        if book.page_count:
            out['pages'] = str(book.page_count)
        if book.print_type:
            out['format'] = book.print_type
        if book.publication_date:
            out['published_year'] = str(book.publication_date.year)
            out['publication_date'] = book.publication_date.isoformat()
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        for full_key, value in (Metafield.objects.for_obj(product, ns='book') or {}).items():
            key = full_key.split('.', 1)[-1]
            if key not in out and value not in (None, ''):
                out[key] = value
    except Exception:  # noqa: BLE001
        pass
    return out


def resolve_slug(field: str, slug: str) -> str | None:
    """Reverse a slug back to the stored value for `field` (e.g. /author/<slug>/)."""
    for value in distinct_values(field):
        if slugify(value) == slug:
            return value
    return None
