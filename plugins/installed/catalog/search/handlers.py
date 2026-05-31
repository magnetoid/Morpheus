"""Hook subscribers — keep the Typesense index in sync with product writes.

We dispatch the upsert via Celery (.delay) so the request thread isn't
blocked on the Typesense round-trip. Indexer failure on a single
product never breaks the response — the nightly reindex task will
heal any drift.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger('morpheus.catalog.search.handlers')


def on_product_created(*, product: Any = None, **_: Any) -> None:
    _dispatch_upsert(product)


def on_product_updated(*, product: Any = None, **_: Any) -> None:
    _dispatch_upsert(product)


def _dispatch_upsert(product: Any) -> None:
    if product is None:
        return
    try:
        from plugins.installed.catalog.search.tasks import upsert_product_task  # noqa: PLC0415

        upsert_product_task.delay(str(product.pk))
    except Exception:  # noqa: BLE001 — never break the product save on indexer queue failure
        logger.exception(
            'catalog.search: upsert dispatch failed for %s', getattr(product, 'pk', '?')
        )
