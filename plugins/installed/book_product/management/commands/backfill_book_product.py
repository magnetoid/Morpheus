"""Backfill BookProduct rows from legacy `book.*` metafields.

This command exists for the transition period where older imports / seed data
still land in the metafields plugin, while the new dashboard + GraphQL book
workflow writes to `plugins.installed.book_product.models.BookProduct`.

Default mode is a dry-run. Pass `--apply` to persist changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from plugins.installed.book_product.models import BookProduct, PaperType, PrintType
from plugins.installed.catalog.models import Product

_TEXT_FIELDS: dict[str, tuple[str, ...]] = {
    'author': ('author',),
    'subtitle': ('subtitle',),
    'publisher': ('publisher',),
    'imprint': ('imprint',),
    'edition': ('edition',),
    # `language` is handled by the dedicated normalization block below
    # (English → en, etc.), not as a raw text field.
    'series': ('series',),
    'series_position': ('series_position', 'series_number'),
    'synopsis': ('synopsis', 'description'),
    'binding': ('binding',),
}

_SPECIAL_FIELDS: dict[str, tuple[str, ...]] = {
    'print_type': ('print_type', 'format'),
    'paper_type': ('paper_type',),
    'page_count': ('page_count', 'pages'),
    'width_mm': ('width_mm', 'width'),
    'height_mm': ('height_mm', 'height'),
    'spine_mm': ('spine_mm', 'spine'),
    'weight_g': ('weight_g', 'weight'),
    'publication_date': ('publication_date',),
}

_LANGUAGE_MAP = {
    'en': 'en',
    'eng': 'en',
    'english': 'en',
    'fr': 'fr',
    'fra': 'fr',
    'fre': 'fr',
    'french': 'fr',
    'de': 'de',
    'deu': 'de',
    'ger': 'de',
    'german': 'de',
    'es': 'es',
    'spa': 'es',
    'spanish': 'es',
    'it': 'it',
    'ita': 'it',
    'italian': 'it',
    'sr': 'sr',
    'srp': 'sr',
    'serbian': 'sr',
}

_PRINT_TYPE_MAP = {
    'hardcover': PrintType.HARDCOVER,
    'hard cover': PrintType.HARDCOVER,
    'hc': PrintType.HARDCOVER,
    'paperback': PrintType.PAPERBACK,
    'paper back': PrintType.PAPERBACK,
    'softcover': PrintType.PAPERBACK,
    'soft cover': PrintType.PAPERBACK,
    'mass market paperback': PrintType.MASS_MARKET,
    'mass-market paperback': PrintType.MASS_MARKET,
    'mass market': PrintType.MASS_MARKET,
    'board book': PrintType.BOARD_BOOK,
    'spiral': PrintType.SPIRAL,
    'wire-o': PrintType.SPIRAL,
    'wire bound': PrintType.SPIRAL,
    'leather': PrintType.LEATHER,
    'cloth bound': PrintType.LEATHER,
    'leather / cloth bound': PrintType.LEATHER,
    'ebook': PrintType.EBOOK,
    'e-book': PrintType.EBOOK,
    'audiobook': PrintType.AUDIOBOOK,
    'audio book': PrintType.AUDIOBOOK,
}

_PAPER_TYPE_MAP = {
    'standard': PaperType.STANDARD,
    'standard white': PaperType.STANDARD,
    'white': PaperType.STANDARD,
    'cream': PaperType.CREAM,
    'cream / off-white': PaperType.CREAM,
    'off-white': PaperType.CREAM,
    'coated gloss': PaperType.COATED_GLOSS,
    'gloss': PaperType.COATED_GLOSS,
    'coated matte': PaperType.COATED_MATTE,
    'matte': PaperType.COATED_MATTE,
    'uncoated': PaperType.UNCOATED,
    'recycled': PaperType.RECYCLED,
}


def _clean(raw: Any) -> str:
    return str(raw or '').strip()


def _normalize_language(raw: Any) -> str:
    value = _clean(raw)
    if not value:
        return ''
    lowered = value.lower()
    return _LANGUAGE_MAP.get(lowered, lowered)


def _normalize_print_type(raw: Any) -> str:
    value = _clean(raw)
    if not value:
        return ''
    lowered = value.lower()
    return _PRINT_TYPE_MAP.get(lowered, lowered if lowered in PrintType.values else '')


def _normalize_paper_type(raw: Any) -> str:
    value = _clean(raw)
    if not value:
        return ''
    lowered = value.lower()
    return _PAPER_TYPE_MAP.get(lowered, lowered if lowered in PaperType.values else '')


def _normalize_int(raw: Any) -> int | None:
    value = _clean(raw)
    if not value:
        return None
    digits = ''.join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


def _normalize_date(raw: Any):
    value = _clean(raw)
    if not value or (len(value) == 4 and value.isdigit()):
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _pick(meta: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in meta and _clean(meta[key]):
            return meta[key]
    return None


def _is_empty(model_value: Any) -> bool:
    return model_value in (None, '')


class Command(BaseCommand):
    help = (
        'Backfill BookProduct columns from legacy book.* metafields. '
        'Dry-run by default; pass --apply to persist.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist the computed changes.')
        parser.add_argument(
            '--overwrite', action='store_true', help='Overwrite non-empty BookProduct fields.'
        )
        parser.add_argument('--product-slug', help='Limit to a single product slug.')

    def handle(self, *args, **options):  # noqa: PLR0912, PLR0915
        try:
            from plugins.installed.metafields.models import Metafield  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f'metafields plugin unavailable: {exc}') from exc

        slug = (options.get('product_slug') or '').strip()
        apply = bool(options.get('apply'))
        overwrite = bool(options.get('overwrite'))

        ct = ContentType.objects.get_for_model(Product)
        product_qs = Product.objects.all().order_by('slug')
        if slug:
            product_qs = product_qs.filter(slug=slug)
        products = list(product_qs)
        if slug and not products:
            raise CommandError(f'No product with slug {slug!r}.')

        product_ids = [str(product.pk) for product in products]
        rows = Metafield.objects.filter(
            content_type=ct,
            namespace='book',
            object_id__in=product_ids,
        ).values_list('object_id', 'key', 'value')

        meta_by_product: dict[str, dict[str, Any]] = {}
        for object_id, key, value in rows:
            meta_by_product.setdefault(str(object_id), {})[str(key)] = value

        created = updated = skipped = unchanged = 0
        for product in products:
            meta = meta_by_product.get(str(product.pk), {})
            if not meta:
                skipped += 1
                continue

            book = BookProduct.objects.filter(product=product).first()
            was_created = book is None
            if book is None:
                book = BookProduct(product=product)
            changes: dict[str, Any] = {}

            for field, keys in _TEXT_FIELDS.items():
                raw = _pick(meta, keys)
                if raw is None:
                    continue
                if not overwrite and not was_created and not _is_empty(getattr(book, field)):
                    continue
                changes[field] = _clean(raw)

            for field, keys in _SPECIAL_FIELDS.items():
                raw = _pick(meta, keys)
                if raw is None:
                    continue
                if not overwrite and not was_created and not _is_empty(getattr(book, field)):
                    continue
                if field == 'print_type':
                    value = _normalize_print_type(raw)
                elif field == 'paper_type':
                    value = _normalize_paper_type(raw)
                elif field == 'publication_date':
                    value = _normalize_date(raw)
                elif field == 'language':
                    value = _normalize_language(raw)
                else:
                    value = _normalize_int(raw)
                if value in (None, ''):
                    continue
                changes[field] = value

            if 'language' not in changes:
                raw_lang = _pick(meta, ('language',))
                if raw_lang is not None and (overwrite or was_created or _is_empty(book.language)):
                    value = _normalize_language(raw_lang)
                    if value:
                        changes['language'] = value

            if not changes:
                unchanged += 1
                continue

            preview = ', '.join(f'{k}={v!r}' for k, v in sorted(changes.items()))
            self.stdout.write(f'{product.slug}: {preview}')

            if apply:
                for field, value in changes.items():
                    setattr(book, field, value)
                book.save()
                if was_created:
                    created += 1
                else:
                    updated += 1
            else:
                unchanged += 1

        mode = 'APPLIED' if apply else 'DRY-RUN'
        self.stdout.write(
            self.style.SUCCESS(
                f'[{mode}] products={len(products)} created={created} updated={updated} '
                f'skipped={skipped} unchanged={unchanged}'
            )
        )
