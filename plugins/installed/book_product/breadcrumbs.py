"""A book's place in the store: its genre page (v0.161.0).

Answers PRODUCT_BREADCRUMB_CATEGORY. A book with an active genre sits under that
genre's page (`/genre/<slug>/`, mounted by this app) in its product page's trail,
the visible one and the BreadcrumbList alike: Home › All books › <genre> › <book>.
The genre is the one a book card names (cards.py: the first active genre in the
genres' own order). Anything else keeps the storefront's category crumbs.
"""

from __future__ import annotations


def genre_crumbs(product, request) -> list[dict]:
    """[{'name', 'url'}] for the book's genre page; [] when it is not a book with one."""
    from plugins.installed.book_product.models import BookProduct

    if product is None or request is None:
        return []
    pk = getattr(product, 'pk', None)
    slug = product.get('slug') if isinstance(product, dict) else None
    if pk is not None:
        book = BookProduct.objects.filter(product_id=pk).first()
    elif slug:
        book = BookProduct.objects.filter(product__slug=slug).first()
    else:
        return []
    if book is None:
        return []
    genre = book.genres.filter(is_active=True).order_by('sort_order', 'name').first()
    if genre is None:
        return []
    return [{'name': genre.name, 'url': request.build_absolute_uri(f'/genre/{genre.slug}/')}]
