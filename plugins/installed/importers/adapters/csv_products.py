"""CSV importer / exporter for the catalog.

Schema (header row, in any order):
    sku, name, slug, price, currency, status, short_description,
    description, weight, category_slug, is_featured, compare_at_price

Rows are upserted by SKU when present, else by slug. Idempotent.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import IO

from django.utils.text import slugify
from djmoney.money import Money

from plugins.installed.importers.base import BaseImporter

logger = logging.getLogger('morpheus.importers.csv')


CSV_FIELDS = [
    'sku',
    'name',
    'slug',
    'price',
    'currency',
    'status',
    'short_description',
    'description',
    'weight',
    'category_slug',
    'is_featured',
    'compare_at_price',
]


class CsvProductImporter(BaseImporter):
    source = 'csv'

    def __init__(self, *, file: IO[str] | None = None, rows: Iterable[dict] | None = None) -> None:
        super().__init__()
        if file is None and rows is None:
            raise ValueError('Provide either `file` or `rows`')
        if file is not None:
            self._rows = list(csv.DictReader(file))
        else:
            self._rows = list(rows or [])

    def _run(self) -> None:
        from plugins.installed.catalog.models import Category, Product

        for row in self._rows:
            try:
                self._upsert_row(row, Product=Product, Category=Category)
                self.summary.increment('product_upserted')
            except Exception as e:  # noqa: BLE001
                self.summary.increment('product_errored')
                self.summary.errors.append(f'{row.get("sku") or row.get("slug")}: {e}')
                logger.warning('csv import row failed: %s', e)

    def _upsert_row(self, row: dict, *, Product, Category) -> None:
        sku = (row.get('sku') or '').strip()
        name = (row.get('name') or '').strip()
        slug = (row.get('slug') or slugify(name)).strip()
        if not name or not slug:
            raise ValueError('row missing name/slug')

        price = _money(row.get('price'), row.get('currency') or 'USD')
        compare = _money(
            row.get('compare_at_price'), row.get('currency') or 'USD', allow_blank=True
        )

        defaults = {
            'name': name[:300],
            'short_description': (row.get('short_description') or '')[:5_000],
            'description': row.get('description') or '',
            'status': (row.get('status') or 'draft').strip().lower()[:10],
            'is_featured': _bool(row.get('is_featured')),
        }
        if price is not None:
            defaults['price'] = price
        if compare is not None:
            defaults['compare_at_price'] = compare
        weight = row.get('weight')
        if weight:
            try:  # noqa: SIM105
                defaults['weight'] = Decimal(str(weight))
            except (InvalidOperation, TypeError):
                pass
        cat_slug = (row.get('category_slug') or '').strip()
        if cat_slug:
            cat, _ = Category.objects.get_or_create(
                slug=cat_slug, defaults={'name': cat_slug.replace('-', ' ').title()}
            )
            defaults['category'] = cat

        if sku:
            obj, created = Product.objects.update_or_create(
                sku=sku, defaults={'slug': slug, **defaults}
            )
        else:
            obj, created = Product.objects.update_or_create(slug=slug, defaults=defaults)
        self.upsert(source_id=sku or slug, dest_obj=obj)


def _money(value, currency: str, *, allow_blank: bool = False):
    if value is None or value == '':
        return None if allow_blank else Money(Decimal('0'), currency)
    try:
        return Money(Decimal(str(value)), currency)
    except (InvalidOperation, TypeError):
        return None if allow_blank else Money(Decimal('0'), currency)


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y'}


def export_products_csv(*, queryset=None) -> str:
    """Render a queryset of Product to a CSV string."""
    from plugins.installed.catalog.models import Product

    qs = queryset if queryset is not None else Product.objects.all()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for p in qs.iterator():
        writer.writerow(
            {
                'sku': p.sku or '',
                'name': p.name,
                'slug': p.slug,
                'price': str(p.price.amount) if p.price else '',
                'currency': str(p.price.currency) if p.price else 'USD',
                'status': p.status,
                'short_description': p.short_description or '',
                'description': p.description or '',
                'weight': str(p.weight) if p.weight else '',
                'category_slug': p.category.slug if p.category_id else '',
                'is_featured': '1' if p.is_featured else '0',
                'compare_at_price': str(p.compare_at_price.amount) if p.compare_at_price else '',
            }
        )
    return out.getvalue()
