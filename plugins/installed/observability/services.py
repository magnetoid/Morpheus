"""Rollup helpers that turn OutboxEvent rows into MerchantMetric buckets."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from django.db import DatabaseError, transaction

logger = logging.getLogger('morpheus.observability')


# Map raw event types -> metric names.
# Anything not listed is not tracked.
_EVENT_METRIC_MAP: dict[str, str] = {
    'order.placed': 'orders_placed',
    'order.paid': 'orders_paid',
    'order.cancelled': 'orders_cancelled',
    'cart.created': 'carts_created',
    'cart.abandoned': 'carts_abandoned',
    'product.viewed': 'product_views',
    'search.performed': 'searches',
    'agent.intent.completed': 'agent_intents_completed',
    'agent.intent.failed': 'agent_intents_failed',
}


def _truncate(ts: datetime, granularity: str) -> datetime:
    if granularity == 'minute':
        return ts.replace(second=0, microsecond=0)
    if granularity == 'hour':
        return ts.replace(minute=0, second=0, microsecond=0)
    if granularity == 'day':
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f'Unknown granularity: {granularity}')


def rollup(*, granularity: str = 'hour', lookback_hours: int = 6) -> int:
    """
    Roll up OutboxEvent rows that landed in the last `lookback_hours` into
    MerchantMetric buckets at the requested granularity. Idempotent: re-running
    the same window never double-counts because we recompute totals from scratch
    using the canonical event log.
    """
    from core.models import OutboxEvent
    from plugins.installed.observability.models import MerchantMetric

    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)

    try:
        events = list(
            OutboxEvent.objects.filter(
                created_at__gte=cutoff, event_type__in=list(_EVENT_METRIC_MAP)
            ).values('event_type', 'created_at', 'payload')
        )
    except DatabaseError as e:
        logger.warning('observability: rollup db error: %s', e)
        return 0

    buckets: dict[tuple[str, str, datetime], dict] = defaultdict(
        lambda: {'value': 0.0, 'sample_count': 0}
    )

    import uuid as _uuid

    for evt in events:
        metric = _EVENT_METRIC_MAP[evt['event_type']]
        raw = (evt.get('payload') or {}).get('channel_id') or ''
        try:
            channel_id = str(_uuid.UUID(raw)) if raw else ''
        except (TypeError, ValueError):
            channel_id = ''  # unknown / invalid — bucket as null channel
        bucket = _truncate(evt['created_at'].astimezone(UTC), granularity)
        key = (channel_id, metric, bucket)
        buckets[key]['value'] += 1
        buckets[key]['sample_count'] += 1

    written = 0
    with transaction.atomic():
        for (channel_id, metric, bucket), agg in buckets.items():
            MerchantMetric.objects.update_or_create(
                channel_id=channel_id or None,
                metric=metric,
                granularity=granularity,
                bucket=bucket,
                defaults={
                    'value': agg['value'],
                    'sample_count': agg['sample_count'],
                },
            )
            written += 1
    logger.info('observability: rollup wrote %s buckets', written)
    return written


def record_error(
    *,
    source: str,
    message: str,
    stack_trace: str = '',
    channel=None,
    metadata: dict | None = None,
) -> None:
    """DEPRECATED shim — forwards to the core error system (ADR 0025).

    Error capture is a core system (`core/errors`); this string-based wrapper is
    kept only for back-compat so any lingering caller still lands in the unified,
    fingerprinted core table instead of the retired plugin ErrorEvent. New code
    should call `core.errors.services.record_error`/`record_message` directly.
    """
    from core.errors.services import record_message

    record_message(
        message,
        kind='server',
        source=source,
        stack_trace=stack_trace,
        extra=metadata or {},
    )


def supported_metrics() -> Iterable[str]:
    return sorted(set(_EVENT_METRIC_MAP.values()))
