"""Backfill: re-home the books that 0006 missed.

0006 only re-homed products that already had a ``BookProduct`` row — but most
catalog books still carry their attributes as legacy ``book.*`` metafields and
have no row yet, so they stayed on their old genre-categories and those
categories survived. Result: genre pages showed a fraction of their books.

This completes the collapse by iterating *products* (not BookProducts): for
every product still on a non-Books category, ensure a BookProduct row exists,
copy its category + additional_categories into ``genres`` (the Genres 0006
created share the old category slugs), re-home it under Books, and clear the
extras. Then delete the emptied old categories — leaving only Books.

Idempotent (safe to re-run); per-product failures are skipped; atomic (an
unexpected error rolls back). Irreversible — reverse is a no-op.
"""

from django.db import migrations
from django.db.models import Q


def forwards(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Product = apps.get_model('catalog', 'Product')
    BookProduct = apps.get_model('book_product', 'BookProduct')
    Genre = apps.get_model('book_product', 'Genre')

    books = Category.objects.filter(slug='books').first()
    if books is None:
        return  # 0006 should have created it; nothing to do otherwise.

    genres_by_slug = {g.slug: g for g in Genre.objects.all()}
    old_cats = list(Category.objects.exclude(pk=books.pk))
    if not old_cats:
        return
    old_slug_by_id = {c.id: c.slug for c in old_cats}

    stale_ids = set(
        Product.objects.filter(
            Q(category__in=old_cats) | Q(additional_categories__in=old_cats)
        ).values_list('id', flat=True)
    )
    for pid in stale_ids:
        try:
            product = Product.objects.get(pk=pid)
            genre_slugs = set()
            if product.category_id in old_slug_by_id:
                genre_slugs.add(old_slug_by_id[product.category_id])
            for sid in product.additional_categories.values_list('id', flat=True):
                if sid in old_slug_by_id:
                    genre_slugs.add(old_slug_by_id[sid])
            book, _ = BookProduct.objects.get_or_create(product=product)
            for slug in genre_slugs:
                genre = genres_by_slug.get(slug)
                if genre is not None:
                    book.genres.add(genre)
            if product.category_id != books.pk:
                product.category = books
                product.save(update_fields=['category'])
            product.additional_categories.clear()
        except Exception:  # noqa: BLE001 — one bad product must not fail the run
            continue

    for cat in old_cats:
        if Product.objects.filter(Q(category=cat) | Q(additional_categories=cat)).exists():
            continue
        if Category.objects.filter(parent=cat).exists():
            continue
        cat.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('book_product', '0006_categories_to_genres'),
        ('catalog', '0014_product_additional_categories'),
    ]

    operations = [migrations.RunPython(forwards, noop)]
