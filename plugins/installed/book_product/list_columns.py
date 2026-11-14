"""The dashboard product list's Author and Genres columns (PRODUCT_LIST_COLUMNS).

A book is filed by genre, not by catalog category (Genre replaced the old
category-as-genre), so on a book store the list's Category column is empty and the
genres are what a merchant looks for. The columns show only on a page that lists a
book, and leave with the app when it is switched off.
"""

from __future__ import annotations


def annotate(products) -> bool:
    """Set ``book_author`` and ``book_genres`` on each product; True when any is a book.

    Two queries for the whole page (the books, then their genres), never one per row.
    """
    from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

    books = {
        b.product_id: b
        for b in BookProduct.objects.filter(product_id__in=[p.pk for p in products])
        .only('product_id', 'author')
        .prefetch_related('genres')
    }
    for p in products:
        book = books.get(p.pk)
        p.book_author = book.author if book else ''
        p.book_genres = [g.name for g in book.genres.all() if g.is_active] if book else []
    return bool(books)


def on_product_list_columns(value, products=None, **_):
    if not products or not annotate(products):
        return value
    value.append(
        {
            'key': 'author',
            'label': 'Author',
            'cell_template': 'book_product/_list_author_cell.html',
            'order': 20,
        }
    )
    value.append(
        {
            'key': 'genres',
            'label': 'Genres',
            'cell_template': 'book_product/_list_genres_cell.html',
            'order': 21,
        }
    )
    return value
