"""Trust-signal data fetchers.

One function per signal kind. Each is independent and graceful — a
failure in one signal must not break the PDP. Aggressively cached
per-product since these queries fan out across the whole catalog
and we want the trust strip to add zero perceptible latency.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger('morpheus.trust_signals')

# Cache windows. Tuned for "freshness vs. DB-load" — the signals don't
# need to be real-time; a 5-minute lag is invisible to customers.
CACHE_TTL_RATING = 300
CACHE_TTL_VERIFIED = 600
CACHE_TTL_RECENT = 60  # ticker feels stale fast — refresh more often

DEFAULT_RECENT_WINDOW_HOURS = 72


def collect_trust_data(product, *, config: dict | None = None) -> dict[str, Any]:
    """Single entry point — returns everything the template needs.

    Per-product cache key. Failure of any one signal returns a partial
    dict — the template hides whichever keys are missing.
    """
    cfg = config or {}
    pk = getattr(product, 'pk', None)
    if pk is None:
        return {}

    data: dict[str, Any] = {}

    if cfg.get('show_rating', True):
        data['rating'] = _get_rating(product, cfg)

    if cfg.get('show_verified_share', True):
        data['verified'] = _get_verified_share(product)

    if cfg.get('show_recent_purchases', True):
        data['recent_purchases'] = _get_recent_purchases(product, cfg)

    return data


# ---------------------------------------------------------------------------
# Rating
# ---------------------------------------------------------------------------


def _get_rating(product, cfg: dict) -> dict | None:
    """Returns {avg, count, stars_filled, stars_half, stars_empty} or
    None if below threshold.
    """
    key = f'ts:rating:{product.pk}'
    cached = cache.get(key)
    if cached is not None:
        return cached if cached != _SENTINEL_HIDDEN else None

    try:
        count = product.review_count  # property on catalog.Product
        if count < cfg.get('min_reviews_for_rating', 3):
            cache.set(key, _SENTINEL_HIDDEN, CACHE_TTL_RATING)
            return None

        avg = product.average_rating  # 0–5 decimal
        if avg is None:
            cache.set(key, _SENTINEL_HIDDEN, CACHE_TTL_RATING)
            return None

        filled = int(avg)
        half = 1 if (avg - filled) >= 0.25 and (avg - filled) < 0.75 else 0
        if (avg - filled) >= 0.75:
            filled += 1
        empty = 5 - filled - half

        result = {
            'avg': round(avg, 1),
            'count': count,
            'stars_filled': filled,
            'stars_half': half,
            'stars_empty': empty,
        }
        cache.set(key, result, CACHE_TTL_RATING)
        return result
    except Exception:  # noqa: BLE001 — never break the PDP
        logger.exception('trust_signals: rating fetch failed for product=%s', product.pk)
        return None


# ---------------------------------------------------------------------------
# Verified-buyer share
# ---------------------------------------------------------------------------


def _get_verified_share(product) -> dict | None:
    """Returns {percent, total} or None if total is too low."""
    key = f'ts:verified:{product.pk}'
    cached = cache.get(key)
    if cached is not None:
        return cached if cached != _SENTINEL_HIDDEN else None

    try:
        agg = product.reviews.filter(is_approved=True).aggregate(
            total=Count('id'),
            verified=Count('id', filter=Q(is_verified_purchase=True)),
        )
        total = agg.get('total', 0) or 0
        verified = agg.get('verified', 0) or 0
        if total < 5:
            cache.set(key, _SENTINEL_HIDDEN, CACHE_TTL_VERIFIED)
            return None

        percent = round((verified / total) * 100)
        # Only show if it's actually a trust signal — < 50% sends the
        # wrong message.
        if percent < 50:
            cache.set(key, _SENTINEL_HIDDEN, CACHE_TTL_VERIFIED)
            return None

        result = {'percent': percent, 'total': total}
        cache.set(key, result, CACHE_TTL_VERIFIED)
        return result
    except Exception:  # noqa: BLE001 — never break the PDP
        logger.exception('trust_signals: verified-share fetch failed for product=%s', product.pk)
        return None


# ---------------------------------------------------------------------------
# Recent purchases ticker
# ---------------------------------------------------------------------------


def _get_recent_purchases(product, cfg: dict) -> dict | None:
    """Returns {count, window_hours, plural_label} or None if below threshold.

    Counts unique orders containing this product (not line items) so a
    bulk order doesn't inflate the count.
    """
    window_hours = int(cfg.get('recent_purchases_window_hours', DEFAULT_RECENT_WINDOW_HOURS))
    min_count = int(cfg.get('min_recent_purchases', 3))

    key = f'ts:recent:{product.pk}:{window_hours}'
    cached = cache.get(key)
    if cached is not None:
        return cached if cached != _SENTINEL_HIDDEN else None

    try:
        OrderItem = _order_item_model()
        if OrderItem is None:
            return None

        since = timezone.now() - timedelta(hours=window_hours)
        count = (
            OrderItem.objects.filter(
                product=product,
                order__placed_at__gte=since,
            )
            .values('order_id')
            .distinct()
            .count()
        )

        if count < min_count:
            cache.set(key, _SENTINEL_HIDDEN, CACHE_TTL_RECENT)
            return None

        result = {
            'count': count,
            'window_hours': window_hours,
            'plural_label': _plural_window_label(window_hours),
        }
        cache.set(key, result, CACHE_TTL_RECENT)
        return result
    except Exception:  # noqa: BLE001 — never break the PDP
        logger.exception('trust_signals: recent-purchases fetch failed for product=%s', product.pk)
        return None


def _plural_window_label(hours: int) -> str:
    if hours <= 1:
        return 'the last hour'
    if hours < 24:
        return f'the last {hours} hours'
    days = round(hours / 24)
    if days == 1:
        return 'the last day'
    if days < 7:
        return f'the last {days} days'
    return f'the last {round(days / 7)} weeks'


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

# Cache sentinel — distinguishes "this product has no signal" from
# "we haven't computed it yet". `None` means "not in cache"; this
# sentinel means "we computed it and the answer is hidden".
_SENTINEL_HIDDEN = '__hidden__'


def _order_item_model():
    """Lazy resolution — orders may not be loaded at import time."""
    from django.apps import apps  # noqa: PLC0415

    try:
        return apps.get_model('orders', 'OrderItem')
    except LookupError:
        return None
