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


# --- Per-visitor merchandising (PRODUCT_LIST_REORDER) ----------------------
# Reorder a storefront product list so the books this visitor is most likely to
# buy come first — same slots, dynamic per-visitor order. Signal = embedding
# similarity to the visitor's recently-viewed books (from the analytics event
# log) blended with co-purchase affinity. Consent-gated; a no-op (original
# order) without functional consent, view history, or embeddings.

_RECENT_LIMIT = 12
_W_EMBED = 1.0
_W_COPURCHASE = 0.5
_ALREADY_VIEWED_PENALTY = 0.15


def _recent_product_ids(request) -> list[str]:
    """Product ids the visitor recently viewed (newest-first, de-duped), read
    from the analytics event log. Empty if analytics is unavailable or there's
    no history for this visitor's cookie."""
    try:
        from plugins.installed.analytics.models import (  # noqa: PLC0415
            AnalyticsEvent,
            AnalyticsSession,
        )
        from plugins.installed.analytics.services import COOKIE_NAME  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — analytics plugin may be disabled
        return []
    cookie_id = (request.COOKIES.get(COOKIE_NAME) or '').strip()
    if not cookie_id:
        return []
    session = AnalyticsSession.objects.filter(cookie_id=cookie_id).only('id').first()
    if session is None:
        return []
    slugs = (
        AnalyticsEvent.objects.filter(session=session, kind='product_view')
        .exclude(product_slug='')
        .order_by('-created_at')
        .values_list('product_slug', flat=True)[: _RECENT_LIMIT * 3]
    )
    seen: set[str] = set()
    ordered: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            ordered.append(s)
        if len(ordered) >= _RECENT_LIMIT:
            break
    if not ordered:
        return []
    from plugins.installed.catalog.models import Product  # noqa: PLC0415

    id_by_slug = dict(Product.objects.filter(slug__in=ordered).values_list('slug', 'id'))
    return [str(id_by_slug[s]) for s in ordered if s in id_by_slug]


def _embeddings_for(ids) -> dict[str, list]:
    try:
        from plugins.installed.ai_assistant.models import ProductEmbedding  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — ai_assistant may be disabled
        return {}
    out: dict[str, list] = {}
    for pid, vec in ProductEmbedding.objects.filter(product_id__in=ids).values_list(
        'product_id', 'vector'
    ):
        if vec:
            out[str(pid)] = vec
    return out


def _centroid(vectors: list) -> list | None:
    vectors = [v for v in vectors if v]
    if not vectors:
        return None
    dim = len(vectors[0])
    acc = [0.0] * dim
    n = 0
    for v in vectors:
        if len(v) != dim:
            continue
        for i in range(dim):
            acc[i] += v[i]
        n += 1
    return [x / n for x in acc] if n else None


def _copurchase_affinity(anchor_ids) -> dict[str, float]:
    from plugins.installed.personalisation.models import CoPurchaseScore  # noqa: PLC0415

    out: dict[str, float] = {}
    for rid, score in CoPurchaseScore.objects.filter(anchor_id__in=anchor_ids).values_list(
        'related_id', 'score'
    ):
        key = str(rid)
        out[key] = max(out.get(key, 0.0), float(score or 0.0))
    mx = max(out.values(), default=0.0)
    return {k: v / mx for k, v in out.items()} if mx > 0 else out


def rank_for_visitor(request, products, *, surface: str = ''):
    """Reorder `products` by per-visitor purchase propensity.

    Returns the *original* order unchanged when there's nothing to personalise
    with — fewer than two items, a non-Product list (e.g. GraphQL dicts), no
    functional consent, no view history, or no usable signal.
    """
    from plugins.installed.personalisation.templatetags.personalisation import (  # noqa: PLC0415
        _has_consent,
    )

    items = list(products)
    if len(items) < 2 or request is None:
        return items
    if not all(hasattr(p, 'pk') for p in items):
        return items
    if not _has_consent(request):
        return items

    recent = _recent_product_ids(request)
    if not recent:
        return items

    cand_ids = [str(p.pk) for p in items]
    vectors = _embeddings_for(list(set(cand_ids) | set(recent)))
    interest = _centroid([vectors[r] for r in recent if r in vectors])
    copurch = _copurchase_affinity(recent)
    if interest is None and not copurch:
        return items

    from core.embeddings import cosine_similarity  # noqa: PLC0415

    recent_set = set(recent)

    def score(p) -> float:
        pid = str(p.pk)
        s = 0.0
        vec = vectors.get(pid)
        if interest is not None and vec:
            s += _W_EMBED * cosine_similarity(interest, vec)
        s += _W_COPURCHASE * copurch.get(pid, 0.0)
        if pid in recent_set:
            s -= _ALREADY_VIEWED_PENALTY  # favour discovery over re-showing
        return s

    order = sorted(range(len(items)), key=lambda i: (-score(items[i]), i))
    return [items[i] for i in order]
