"""Canonical product identifier codes (ISBN, GTIN/EAN, UPC, MPN, ASIN…).

Stored as metafields in the ``identifiers`` namespace — no model columns,
works for any product type (the future-proof commerce path). ISBN-13 falls
back to the legacy ``book.isbn`` metafield so existing book data keeps
surfacing. ONE registry drives the PDP display, the product editor, and the
schema.org Product JSON-LD, so the supported set never drifts between them.
"""

# ruff: noqa: PLC0415
# Inline import keeps this module importable before the app registry +
# metafields models are ready.

from __future__ import annotations

IDENTIFIERS_NAMESPACE = 'identifiers'

# (key, label, schema.org Product property | None, input placeholder)
PRODUCT_IDENTIFIERS: tuple[tuple[str, str, str | None, str], ...] = (
    ('isbn13', 'ISBN-13', 'isbn', '978…'),
    ('isbn10', 'ISBN-10', None, ''),
    ('ean13', 'EAN / GTIN-13', 'gtin13', ''),
    ('upc', 'UPC / GTIN-12', 'gtin12', ''),
    ('gtin14', 'GTIN-14', 'gtin14', ''),
    ('mpn', 'MPN (manufacturer part no.)', 'mpn', ''),
    ('asin', 'ASIN', 'asin', ''),
    ('barcode', 'Barcode', None, ''),
)


def product_identifiers(instance) -> list[dict]:
    """Codes present on ``instance`` → ``[{key, label, value, jsonld}]``.

    Reads the ``identifiers`` namespace, with a legacy fallback: when no
    ``identifiers.isbn13`` is set, use ``book.isbn``. Fail-soft to ``[]``.
    """
    if instance is None:
        return []
    try:
        from plugins.installed.metafields.models import Metafield

        ids = Metafield.objects.for_obj(instance, ns=IDENTIFIERS_NAMESPACE) or {}
        book = Metafield.objects.for_obj(instance, ns='book') or {}
        # for_obj keys are "namespace.key" (see _book_specs); fall back to bare.
        legacy_isbn = book.get('book.isbn') or book.get('isbn')
    except Exception:  # noqa: BLE001 — never break a page over identifiers
        return []
    out: list[dict] = []
    for key, label, jsonld, _placeholder in PRODUCT_IDENTIFIERS:
        value = ids.get(f'{IDENTIFIERS_NAMESPACE}.{key}') or ids.get(key)
        if not value and key == 'isbn13' and legacy_isbn:
            value = legacy_isbn
        if value in (None, ''):
            continue
        out.append({'key': key, 'label': label, 'value': str(value).strip(), 'jsonld': jsonld})
    return out


def identifier_values(instance) -> dict:
    """``{key: value}`` for editor pre-fill — all canonical keys, '' if unset.

    Unlike ``product_identifiers`` this does NOT apply the book.isbn legacy
    fallback (the editor writes the ``identifiers`` namespace directly).
    """
    try:
        from plugins.installed.metafields.models import Metafield

        ids = Metafield.objects.for_obj(instance, ns=IDENTIFIERS_NAMESPACE) or {}
    except Exception:  # noqa: BLE001
        ids = {}
    return {
        key: str(ids.get(f'{IDENTIFIERS_NAMESPACE}.{key}') or ids.get(key) or '')
        for key, _l, _j, _p in PRODUCT_IDENTIFIERS
    }
