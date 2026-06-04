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


_FORMAT_MAP = {
    'paperback': 'paperback',
    'softcover': 'paperback',
    'hardcover': 'hardcover',
    'hardback': 'hardcover',
    'mass market paperback': 'mass_market',
    'mass market': 'mass_market',
    'board book': 'board_book',
    'spiral': 'spiral',
    'ebook': 'ebook',
    'e-book': 'ebook',
    'audiobook': 'audiobook',
    'audio book': 'audiobook',
}
_LANGUAGE_MAP = {
    'english': 'en',
    'eng': 'en',
    'french': 'fr',
    'german': 'de',
    'spanish': 'es',
    'italian': 'it',
}


def set_book_attrs(product, raw: dict) -> None:
    """Upsert a BookProduct from a raw ``book.*``-shaped dict (author, publisher,
    pages, format, published_year, language, …) — used by seeders/importers so
    new books land on the model, not just metafields. Normalizes format →
    print_type, pages → page_count, published_year → publication_date. Fail-soft.
    """
    try:
        from plugins.installed.book_product.models import BookProduct, PrintType  # noqa: PLC0415

        book, _ = BookProduct.objects.get_or_create(product=product)

        def _s(key: str) -> str:
            return str(raw.get(key) or '').strip()

        for src, dst, cap in (
            ('author', 'author', 300),
            ('subtitle', 'subtitle', 300),
            ('publisher', 'publisher', 200),
            ('imprint', 'imprint', 200),
            ('series', 'series', 200),
            ('edition', 'edition', 100),
            ('binding', 'binding', 100),
        ):
            if _s(src):
                setattr(book, dst, _s(src)[:cap])
        if _s('synopsis'):
            book.synopsis = _s('synopsis')
        lang = _s('language').lower()
        if lang:
            book.language = _LANGUAGE_MAP.get(lang, lang[:20])
        fmt = _s('format').lower()
        if fmt in PrintType.values:
            book.print_type = fmt
        elif fmt in _FORMAT_MAP:
            book.print_type = _FORMAT_MAP[fmt]
        pages = _s('pages')
        if pages.isdigit():
            book.page_count = int(pages)
        year = _s('published_year')[:4]
        if year.isdigit() and book.publication_date is None:
            from datetime import date  # noqa: PLC0415

            book.publication_date = date(int(year), 1, 1)
        book.save()
    except Exception:  # noqa: BLE001
        pass


def resolve_slug(field: str, slug: str) -> str | None:
    """Reverse a slug back to the stored value for `field` (e.g. /author/<slug>/)."""
    for value in distinct_values(field):
        if slugify(value) == slug:
            return value
    return None
