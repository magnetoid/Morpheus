"""Multi-touch marketing attribution + ROAS.

The `attribute()` function is a pure, exhaustively-tested revenue splitter across
five industry-standard models. Journeys are reconstructed nightly from each
purchaser's AnalyticsSession UTM sources; per-model per-channel revenue is written
to DailyMetric (analytics owns that table, so no cross-plugin coupling). Ad spend
is pulled from channel plugins via the ANALYTICS_AD_SPEND filter into AdSpendSnapshot.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

MODELS = ('last_touch', 'first_touch', 'linear', 'time_decay', 'position_based')
_HALF_LIFE_DAYS = Decimal(7)
_DIRECT = 'direct'


def _weights(journey: list, model: str) -> list:
    """Per-touch weights (Decimals summing to 1) for a journey of n touches."""
    n = len(journey)
    if n == 1:
        return [Decimal(1)]
    if model == 'first_touch':
        return [Decimal(1)] + [Decimal(0)] * (n - 1)
    if model == 'linear':
        return [Decimal(1) / n] * n
    if model == 'position_based':
        # 40% first / 40% last / 20% split across the middle; n==2 → 50/50.
        edge = Decimal('0.4') if n > 2 else Decimal('0.5')
        mids = [Decimal('0.2') / (n - 2)] * (n - 2) if n > 2 else []
        return [edge, *mids, edge]
    if model == 'time_decay':
        purchase_ts = journey[-1][1]
        raw = []
        for _channel, ts in journey:
            days_before = Decimal(str((purchase_ts - ts).total_seconds() / 86400.0))
            raw.append(Decimal(2) ** (-days_before / _HALF_LIFE_DAYS))
        total = sum(raw) or Decimal(1)
        return [r / total for r in raw]
    # last_touch (default)
    return [Decimal(0)] * (n - 1) + [Decimal(1)]


def attribute(journey: list, revenue, model: str) -> dict:
    """Split `revenue` across a journey `[(channel, timestamp)]` (oldest→newest).

    Returns {channel: Decimal}. Multiple touches on the same channel accumulate.
    """
    rev = Decimal(str(revenue))
    if not journey:
        return {}
    out: dict = defaultdict(Decimal)
    for (channel, _ts), w in zip(journey, _weights(journey, model), strict=True):
        out[channel] += rev * w
    return dict(out)


def _channel_of(session) -> str:
    return (session.utm_source or '').strip().lower() or _DIRECT


def build_journey(customer_id, purchase_ts, lookback_days: int = 30) -> list:
    """A purchaser's touch sequence: their sessions' UTM sources within the
    lookback window before the purchase, oldest→newest."""
    from plugins.installed.analytics.models import AnalyticsSession

    since = purchase_ts - timedelta(days=lookback_days)
    sessions = AnalyticsSession.objects.filter(
        customer_id=customer_id, first_seen_at__gte=since, first_seen_at__lte=purchase_ts
    ).order_by('first_seen_at')
    journey = [(_channel_of(s), s.first_seen_at) for s in sessions]
    return journey or [(_DIRECT, purchase_ts)]


def collect_ad_spend() -> int:
    """Fire ANALYTICS_AD_SPEND, snapshot each channel's spend into AdSpendSnapshot
    for today. Returns rows written."""
    from djmoney.money import Money

    from core.hooks import MorpheusEvents, hook_registry
    from plugins.installed.analytics.models import AdSpendSnapshot

    rows = hook_registry.filter(MorpheusEvents.ANALYTICS_AD_SPEND, value=[]) or []
    today = timezone.now().date()
    written = 0
    for row in rows:
        channel = (row.get('channel') or '').strip().lower()
        spend = row.get('spend')
        if not channel or spend in (None, ''):
            continue
        AdSpendSnapshot.objects.update_or_create(
            day=today,
            channel=channel,
            defaults={'spend': Money(Decimal(str(spend)), 'USD'), 'source_meta': row},
        )
        written += 1
    return written


def attribute_revenue(days: int = 30) -> int:
    """Reconstruct journeys for purchases in the window, apply every model, and
    write per-model per-channel revenue to DailyMetric. Returns purchases processed."""
    from djmoney.money import Money

    from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric

    since = timezone.now() - timedelta(days=days)
    purchases = AnalyticsEvent.objects.filter(
        kind='purchase', created_at__gte=since, customer__isnull=False
    ).values('customer_id', 'created_at', 'revenue', 'revenue_currency')

    # accumulate {(model, channel): Decimal}
    totals: dict = defaultdict(Decimal)
    processed = 0
    for p in purchases:
        rev = p.get('revenue')
        if rev in (None, 0):
            continue
        journey = build_journey(p['customer_id'], p['created_at'], lookback_days=days)
        for model in MODELS:
            for channel, amount in attribute(journey, rev, model).items():
                totals[(model, channel)] += amount
        processed += 1

    today = timezone.now().date()
    for (model, channel), amount in totals.items():
        DailyMetric.objects.update_or_create(
            day=today,
            metric='attribution',
            dimension=f'{model}:{channel}',
            defaults={'value_money': Money(amount.quantize(Decimal('0.01')), 'USD')},
        )
    return processed


def roas_by_channel(model: str = 'last_touch', days: int = 30) -> list:
    """Per-channel spend (AdSpendSnapshot) vs attributed revenue (DailyMetric) → ROAS."""
    from plugins.installed.analytics.models import AdSpendSnapshot, DailyMetric

    since = timezone.now().date() - timedelta(days=days)
    spend: dict = defaultdict(Decimal)
    for row in AdSpendSnapshot.objects.filter(day__gte=since).values('channel', 'spend'):
        spend[row['channel']] += Decimal(str(row['spend'] or 0))

    revenue: dict = defaultdict(Decimal)
    prefix = f'{model}:'
    for row in DailyMetric.objects.filter(
        metric='attribution', dimension__startswith=prefix, day__gte=since
    ).values('dimension', 'value_money'):
        channel = row['dimension'][len(prefix) :]
        revenue[channel] += Decimal(str(row['value_money'] or 0))

    channels = sorted(set(spend) | set(revenue))
    out = []
    for ch in channels:
        s, r = spend[ch], revenue[ch]
        out.append(
            {
                'channel': ch,
                'spend': s,
                'revenue': r,
                'roas': round(r / s, 2) if s else None,
            }
        )
    out.sort(key=lambda x: x['revenue'], reverse=True)
    return out
