"""Background jobs for book taxonomies.

Bulk copy backfill: the storefront ships ~1500 topic pages and ~40 genre
pages, essentially none of which had intro copy — far too many to hand-write,
and the per-page "Generate" button is one-at-a-time. This walks the terms that
actually carry books, most-stocked first, and writes the missing intro + SEO.
"""

# ruff: noqa: PLC0415
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger('morpheus.book_product')

# Hard ceiling per run. Each term is one LLM call, so an unbounded backfill is
# real money and a long-running worker — the caller picks a batch and can
# re-run. Also a guard against mass-generating thin pages for the long tail.
MAX_BATCH = 200


@shared_task(name='book_product.backfill_taxonomy_copy')
def backfill_taxonomy_copy(kind: str, limit: int = 25) -> dict:
    """Write intro + SEO for `limit` curated terms of `kind` that lack it.

    Targets only terms with at least one active book (an empty term's page
    would be bare anyway) and orders by book count descending, so the pages a
    shopper actually lands on get copy first. Returns a
    ``{'written': int, 'skipped': int, 'kind': str}`` summary; a per-term
    provider failure is logged and skipped rather than failing the batch.
    """
    from django.db.models import Count, Q

    from plugins.installed.book_product.services_copy import (
        CopyGenerationError,
        generate_copy,
    )

    model = {'genre': 'Genre', 'topic': 'Topic'}.get(kind)
    if model is None:
        return {'written': 0, 'skipped': 0, 'kind': kind, 'error': 'unknown kind'}
    from plugins.installed.book_product import models as m

    Model = getattr(m, model)

    limit = max(1, min(int(limit or 1), MAX_BATCH))
    targets = list(
        Model.objects.annotate(_n=Count('books', filter=Q(books__product__status='active')))
        .filter(_n__gt=0, description='')
        .order_by('-_n', 'name')[:limit]
    )
    written = skipped = 0
    for obj in targets:
        try:
            payload = generate_copy(kind, obj.slug)
        except (CopyGenerationError, LookupError) as e:
            logger.warning('book_product: copy backfill skipped %s/%s: %s', kind, obj.slug, e)
            skipped += 1
            continue
        if not payload.get('description'):
            skipped += 1
            continue
        obj.description = payload['description']
        # Never clobber SEO the merchant already tuned by hand.
        obj.meta_title = obj.meta_title or payload.get('meta_title', '')
        obj.meta_description = obj.meta_description or payload.get('meta_description', '')
        obj.save(update_fields=['description', 'meta_title', 'meta_description', 'updated_at'])
        written += 1
    logger.info('book_product: copy backfill %s — wrote %s, skipped %s', kind, written, skipped)
    return {'written': written, 'skipped': skipped, 'kind': kind}
