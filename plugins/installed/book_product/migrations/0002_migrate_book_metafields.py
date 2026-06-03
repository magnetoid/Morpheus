"""Move legacy book.* metafields onto BookProduct columns.

Idempotent + fail-soft: copies book.author / book.pages / book.publisher /
book.synopsis into a BookProduct row per product, only filling EMPTY columns
(re-running never clobbers a value edited on the model). Any failure on a
single product is skipped; a missing metafields table is a no-op — the
migration must never block a prod boot.
"""

from __future__ import annotations

from django.db import migrations

_KEYS = ('author', 'pages', 'publisher', 'synopsis')


def migrate_book_metafields(apps, schema_editor):
    BookProduct = apps.get_model('book_product', 'BookProduct')
    Product = apps.get_model('catalog', 'Product')
    try:
        Metafield = apps.get_model('metafields', 'Metafield')
        ContentType = apps.get_model('contenttypes', 'ContentType')
        ct = ContentType.objects.get(app_label='catalog', model='product')
    except Exception:  # noqa: BLE001 — metafields/CT absent -> nothing to migrate
        return

    by_obj: dict[str, dict] = {}
    for mf in Metafield.objects.filter(content_type=ct, namespace='book', key__in=_KEYS):
        by_obj.setdefault(str(mf.object_id), {})[mf.key] = mf.value

    for object_id, vals in by_obj.items():
        try:
            product = Product.objects.filter(pk=object_id).first()
            if product is None:
                continue
            book, _ = BookProduct.objects.get_or_create(product=product)
            changed = False
            if vals.get('author') and not book.author:
                book.author = vals['author'][:300]
                changed = True
            if vals.get('publisher') and not book.publisher:
                book.publisher = vals['publisher'][:200]
                changed = True
            if vals.get('synopsis') and not book.synopsis:
                book.synopsis = vals['synopsis']
                changed = True
            if vals.get('pages') and book.page_count is None:
                try:
                    book.page_count = int(str(vals['pages']).strip())
                    changed = True
                except (ValueError, TypeError):
                    pass
            if changed:
                book.save()
        except Exception:  # noqa: BLE001 — one bad row must not fail the migration
            continue


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('book_product', '0001_initial'),
        ('catalog', '0014_product_additional_categories'),
        ('metafields', '0002_rename_metafields__content_b3f0a2_idx_metafields__content_d5304f_idx_and_more'),
    ]

    operations = [migrations.RunPython(migrate_book_metafields, noop)]
