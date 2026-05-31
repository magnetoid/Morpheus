"""Co-purchase computation + serve-time lookup.

`recompute_copurchases()` runs nightly via Celery Beat. It scans the
last N days of paid orders, builds the symmetric co-occurrence
counts, computes Jaccard similarity for each pair, and writes the
top-K per anchor to CoPurchaseScore.

`related_to(product, k=4)` is the serve-time API the storefront block
calls. O(1) over an indexed query.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger('morpheus.personalisation')

DEFAULT_WINDOW_DAYS = 90
DEFAULT_TOP_K = 12  # store top 12 per anchor; serve 4 at render time
MIN_CO_COUNT = 3  # ignore pairs that only co-occurred 1-2 times
MIN_JACCARD = 0.02


def recompute_copurchases(
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    top_k: int = DEFAULT_TOP_K,
) -> dict:
    """Rebuild the CoPurchaseScore table.

    Pure-Python pass over OrderItem rows in the window — cheap enough
    at < 1M items; for larger catalogs we'd shard by anchor product and
    incrementalise. Returns a dict with counts for the scheduler log.
    """
    from plugins.installed.orders.models import OrderItem  # noqa: PLC0415
    from plugins.installed.personalisation.models import CoPurchaseScore  # noqa: PLC0415

    cutoff = timezone.now() - timedelta(days=window_days)
    qs = OrderItem.objects.filter(
        order__placed_at__gte=cutoff,
        order__status__in=('confirmed', 'paid', 'fulfilled', 'completed'),
    ).values('order_id', 'product_id')

    # Group product ids per order.
    by_order: dict[str, set[str]] = defaultdict(set)
    for row in qs:
        if row['product_id']:
            by_order[row['order_id']].add(row['product_id'])

    # Build co-occurrence + individual counts.
    co_counts: Counter[tuple[str, str]] = Counter()
    individual: Counter[str] = Counter()
    for products in by_order.values():
        for p in products:
            individual[p] += 1
        for a, b in _ordered_pairs(products):
            co_counts[(a, b)] += 1

    # Jaccard similarity per pair, then per anchor pick top-K.
    per_anchor_scores: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for (a, b), co in co_counts.items():
        if co < MIN_CO_COUNT:
            continue
        union = individual[a] + individual[b] - co
        jaccard = co / union if union > 0 else 0.0
        if jaccard < MIN_JACCARD:
            continue
        per_anchor_scores[a].append((b, jaccard, co))
        per_anchor_scores[b].append((a, jaccard, co))

    # Replace the table atomically: wipe + bulk insert top-K per anchor.
    rows_to_create = []
    for anchor, items in per_anchor_scores.items():
        items.sort(key=lambda t: t[1], reverse=True)
        for related, score, co in items[:top_k]:
            rows_to_create.append(
                CoPurchaseScore(
                    anchor_id=anchor,
                    related_id=related,
                    score=score,
                    co_count=co,
                )
            )

    inserted = 0
    from django.db import transaction  # noqa: PLC0415

    with transaction.atomic():
        CoPurchaseScore.objects.all().delete()
        if rows_to_create:
            CoPurchaseScore.objects.bulk_create(
                rows_to_create, batch_size=1000, ignore_conflicts=True
            )
            inserted = len(rows_to_create)

    logger.info(
        'personalisation: %s pairs from %s orders (window=%sd)',
        inserted,
        len(by_order),
        window_days,
    )
    return {
        'pairs': inserted,
        'orders_scanned': len(by_order),
        'window_days': window_days,
    }


def related_to(product, *, k: int = 4) -> list:
    """Return up to k Product instances most-bought-with `product`."""
    if product is None:
        return []
    from plugins.installed.catalog.models import Product  # noqa: PLC0415
    from plugins.installed.personalisation.models import CoPurchaseScore  # noqa: PLC0415

    pair_rows = (
        CoPurchaseScore.objects.filter(anchor_id=product.pk)
        .order_by('-score')
        .values_list('related_id', flat=True)[:k]
    )
    related_ids = list(pair_rows)
    if not related_ids:
        return []
    # Preserve ranked order via dict trick (Python 3.7+ insertion order).
    by_id = {p.pk: p for p in Product.objects.filter(pk__in=related_ids, status='active')}
    return [by_id[pid] for pid in related_ids if pid in by_id]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _ordered_pairs(products: set[str]):
    """Yield each unordered pair exactly once as a sorted tuple."""
    ids = sorted(products)
    n = len(ids)
    for i in range(n):
        for j in range(i + 1, n):
            yield ids[i], ids[j]
