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
# How long a queued run holds its per-kind lock (see dashboard curated_backfill).
# Comfortably longer than a full MAX_BATCH run, but self-expiring so a worker
# that dies mid-batch can't wedge the button shut forever.
BACKFILL_LOCK_SECS = 60 * 30
# Shortest believable 2-3 sentence intro. Guards the AUTO-PUBLISH path only:
# this writes straight to a public page with nobody reading it first, so a
# stunted answer would go live. The dashboard's Generate button deliberately
# does NOT apply this — a human is looking at that result and can judge it.
_MIN_DESCRIPTION_CHARS = 40


def missing_copy_queryset(kind: str):
    """The terms the backfill will actually write, most-stocked first.

    A term qualifies when it carries at least one ACTIVE book (an empty term's
    page would be bare, so copy there is wasted spend) and has no intro yet.

    Shared with the dashboard deliberately: the button's count and the task's
    target set were computed from two different predicates, so a genre whose
    books were all drafts was advertised as "1 missing intro" that the task
    then silently refused to write — the count never moved no matter how often
    you clicked. One predicate, one source of truth.
    """
    from django.db.models import Count, Q

    from plugins.installed.book_product import models as m

    model = {'genre': 'Genre', 'topic': 'Topic'}.get(kind)
    if model is None:
        return None
    return (
        getattr(m, model)
        .objects.annotate(_n=Count('books', filter=Q(books__product__status='active')))
        .filter(_n__gt=0, description='')
        .order_by('-_n', 'name')
    )


@shared_task(name='book_product.backfill_taxonomy_copy')
def backfill_taxonomy_copy(kind: str, limit: int = 25) -> dict:
    """Write intro + SEO for `limit` curated terms of `kind` that lack it.

    Targets only terms with at least one active book (an empty term's page
    would be bare anyway) and orders by book count descending, so the pages a
    shopper actually lands on get copy first. Returns a
    ``{'written': int, 'skipped': int, 'kind': str}`` summary; a per-term
    provider failure is logged and skipped rather than failing the batch.
    """
    from django.core.cache import cache

    qs = missing_copy_queryset(kind)
    if qs is None:
        cache.delete(f'book_product:backfill:{kind}')
        return {'written': 0, 'skipped': 0, 'kind': kind, 'error': 'unknown kind'}

    limit = max(1, min(int(limit or 1), MAX_BATCH))
    targets = list(qs[:limit])
    written = skipped = 0
    try:
        written, skipped = _write_copy(kind, targets)
    finally:
        # Release the enqueue lock as soon as the run ends — success, failure,
        # or crash. Its TTL is only the backstop for a worker that dies without
        # unwinding; holding it the full 30min after a clean run would lock the
        # merchant out of the next batch for no reason.
        cache.delete(f'book_product:backfill:{kind}')
    logger.info('book_product: copy backfill %s — wrote %s, skipped %s', kind, written, skipped)
    return {'written': written, 'skipped': skipped, 'kind': kind}


def _write_copy(kind: str, targets: list) -> tuple[int, int]:
    """Generate + save copy for each target. Returns (written, skipped)."""
    from plugins.installed.book_product.services_copy import (
        CopyGenerationError,
        generate_copy,
    )

    written = skipped = 0
    for obj in targets:
        try:
            payload = generate_copy(kind, obj.slug)
        except (CopyGenerationError, LookupError) as e:
            logger.warning('book_product: copy backfill skipped %s/%s: %s', kind, obj.slug, e)
            skipped += 1
            continue
        description = (payload.get('description') or '').strip()
        if len(description) < _MIN_DESCRIPTION_CHARS:
            # Too short to be the 2-3 sentence intro we asked for — a stunted
            # answer wearing a valid-JSON costume. Skip rather than publish it;
            # a re-run retries the page.
            logger.warning(
                'book_product: copy backfill rejected %s/%s — too short: %r',
                kind,
                obj.slug,
                description,
            )
            skipped += 1
            continue
        obj.description = payload['description']
        # Never clobber SEO the merchant already tuned by hand.
        obj.meta_title = obj.meta_title or payload.get('meta_title', '')
        obj.meta_description = obj.meta_description or payload.get('meta_description', '')
        obj.save(update_fields=['description', 'meta_title', 'meta_description', 'updated_at'])
        written += 1
    return (written, skipped)
