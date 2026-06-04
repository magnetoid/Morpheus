"""Pure-Django fallback search — Product.name + book attributes (model + legacy)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from plugins.installed.catalog.search.dispatcher import SearchResult


def run(q: str, *, page: int = 1, per_page: int = 24) -> SearchResult:
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    # Book-field matches: BookProduct model first, plus a legacy book.* metafield
    # fallback (covers ISBN + un-backfilled books).
    book_ids: set[str] = set()
    try:
        from plugins.installed.book_product.models import BookProduct  # noqa: PLC0415

        book_ids.update(
            str(pid)
            for pid in BookProduct.objects.filter(
                Q(author__icontains=q) | Q(publisher__icontains=q) | Q(series__icontains=q)
            ).values_list('product_id', flat=True)
        )
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        from plugins.installed.metafields.models import Metafield  # noqa: PLC0415

        ct = ContentType.objects.get_for_model(Product)
        book_ids.update(
            str(oid)
            for oid in Metafield.objects.filter(
                content_type=ct,
                namespace='book',
                key__in=('author', 'publisher', 'isbn'),
                value__icontains=q,
            ).values_list('object_id', flat=True)
        )
    except Exception:  # noqa: BLE001, S110
        pass

    base = Product.objects.filter(status='active').filter(
        Q(name__icontains=q)
        | Q(description__icontains=q)
        | Q(slug__icontains=q)
        | Q(sku__icontains=q)
        | Q(pk__in=book_ids)
    )
    total = base.count()
    offset = max(0, (page - 1) * per_page)
    ids = list(
        base.order_by('-created_at').values_list('pk', flat=True)[offset : offset + per_page]
    )
    return SearchResult(product_ids=ids, total=total, backend='django')
