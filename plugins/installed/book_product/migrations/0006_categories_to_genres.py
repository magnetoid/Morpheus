"""Collapse catalog Categories (used as genres) into the new Genre taxonomy.

The storefront only ever had ONE real category — Books — with "categories"
(Fiction, Poetry, Essays, …) standing in for genres. This migration makes that
explicit:

  1. Ensure a single ``Books`` root Category exists.
  2. Turn every other Category into a ``Genre`` (same name/slug/description/SEO),
     so the old ``/category/<slug>/`` slug maps 1:1 to ``/genre/<slug>/``.
  3. For each *book* product, copy its category + additional_categories into
     ``book.genres``, then re-home it under ``Books`` and clear the extras.
  4. Delete the now-empty genre-categories — leaving ``Books`` as the only one.

Safety: a Category still referenced by a NON-book product is kept (non-book
guard); a Category with surviving children is kept (no cascade surprise); the
new ``Books`` root gets MPTT lft/rght/level/tree_id set by hand (the historical
model has no save hook); per-product failures are skipped; the run is atomic so
an unexpected error rolls back. Irreversible — reverse is a no-op.
"""

from django.db import migrations
from django.db.models import Max, Q
from django.utils.text import slugify


def _ensure_books_root(Category):
    books = Category.objects.filter(slug='books').first()
    if books is not None:
        return books
    next_tree = (Category.objects.aggregate(m=Max('tree_id'))['m'] or 0) + 1
    return Category.objects.create(
        name='Books',
        slug='books',
        parent=None,
        is_active=True,
        sort_order=0,
        lft=1,
        rght=2,
        level=0,
        tree_id=next_tree,
    )


def forwards(apps, schema_editor):
    Category = apps.get_model('catalog', 'Category')
    Product = apps.get_model('catalog', 'Product')
    BookProduct = apps.get_model('book_product', 'BookProduct')
    Genre = apps.get_model('book_product', 'Genre')

    books = _ensure_books_root(Category)

    old_cats = list(Category.objects.exclude(pk=books.pk))
    cat_to_genre: dict = {}
    for cat in old_cats:
        slug = cat.slug or slugify(cat.name)
        genre, _ = Genre.objects.get_or_create(
            slug=slug,
            defaults={
                'name': cat.name,
                'description': cat.description or '',
                'meta_title': cat.meta_title or '',
                'meta_description': cat.meta_description or '',
                'image': cat.image.name if cat.image else None,
                'sort_order': cat.sort_order or 0,
                'is_active': cat.is_active,
            },
        )
        cat_to_genre[cat.pk] = genre

    book_product_ids = set(BookProduct.objects.values_list('product_id', flat=True))
    for book in BookProduct.objects.all():
        try:
            product = Product.objects.filter(pk=book.product_id).first()
            if product is None:
                continue
            genre_pks = set()
            if product.category_id in cat_to_genre:
                genre_pks.add(cat_to_genre[product.category_id].pk)
            for ac_id in product.additional_categories.values_list('id', flat=True):
                if ac_id in cat_to_genre:
                    genre_pks.add(cat_to_genre[ac_id].pk)
            if genre_pks:
                book.genres.add(*genre_pks)
            if product.category_id != books.pk:
                product.category = books
                product.save(update_fields=['category'])
            product.additional_categories.clear()
        except Exception:  # noqa: BLE001 — one bad product must not fail the run
            continue

    for cat in old_cats:
        still_used = (
            Product.objects.filter(Q(category=cat) | Q(additional_categories=cat))
            .exclude(pk__in=book_product_ids)
            .exists()
        )
        has_children = Category.objects.filter(parent=cat).exists()
        any_product = Product.objects.filter(Q(category=cat) | Q(additional_categories=cat)).exists()
        if still_used or has_children or any_product:
            continue
        cat.delete()


def noop(apps, schema_editor):
    # Irreversible: deleted Category rows can't be restored. Genres remain.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('book_product', '0005_genre_topic_bookproduct_genres_bookproduct_topics'),
        ('catalog', '0014_product_additional_categories'),
    ]

    operations = [migrations.RunPython(forwards, noop)]
