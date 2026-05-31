"""Celery tasks: full reindex + per-product upsert/delete."""

from __future__ import annotations

from celery import shared_task


@shared_task(name='catalog.search.reindex_all')
def reindex_all_task(batch_size: int = 500) -> dict:
    from plugins.installed.catalog.search.typesense_backend import reindex_all  # noqa: PLC0415

    return reindex_all(batch_size=batch_size)


@shared_task(name='catalog.search.upsert_product')
def upsert_product_task(product_id: str) -> None:
    from plugins.installed.catalog.models import Product  # noqa: PLC0415
    from plugins.installed.catalog.search.typesense_backend import upsert_product  # noqa: PLC0415

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return
    upsert_product(product)


@shared_task(name='catalog.search.delete_product')
def delete_product_task(product_id: str) -> None:
    from plugins.installed.catalog.search.typesense_backend import delete_product  # noqa: PLC0415

    delete_product(str(product_id))
