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


def resolve_slug(field: str, slug: str) -> str | None:
    """Reverse a slug back to the stored value for `field` (e.g. /author/<slug>/)."""
    for value in distinct_values(field):
        if slugify(value) == slug:
            return value
    return None
