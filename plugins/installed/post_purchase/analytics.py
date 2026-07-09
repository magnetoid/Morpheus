"""NPS analytics — aggregations over the NPSResponse table this plugin owns.

Pure ORM, no new tables. Buckets follow NPSResponse.bucket (9-10 promoter,
7-8 passive, 0-6 detractor). NPS = %promoters − %detractors (integer, −100…100).
Response rate uses the JourneyStep 'nps_survey'/'sent' ledger as the denominator
(surveys actually sent) — that ledger is this plugin's own model, so no cross-plugin
coupling. The scores were collected but never aggregated before this module.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone


def _bucket(score: int) -> str:
    if score >= 9:
        return 'promoter'
    if score >= 7:
        return 'passive'
    return 'detractor'


def _nps(promoters: int, detractors: int, total: int) -> int | None:
    if total == 0:
        return None
    return round((promoters - detractors) / total * 100)


def nps_summary(days: int = 90) -> dict:
    """Rolling-window NPS + bucket counts + response rate."""
    from plugins.installed.post_purchase.models import JourneyStep, NPSResponse

    since = timezone.now() - timedelta(days=days)
    counts = {'promoter': 0, 'passive': 0, 'detractor': 0}
    total = 0
    for score in NPSResponse.objects.filter(submitted_at__gte=since).values_list(
        'score', flat=True
    ):
        counts[_bucket(score)] += 1
        total += 1
    sent = JourneyStep.objects.filter(step='nps_survey', status='sent', sent_at__gte=since).count()
    return {
        'nps': _nps(counts['promoter'], counts['detractor'], total),
        'promoters': counts['promoter'],
        'passives': counts['passive'],
        'detractors': counts['detractor'],
        'responses': total,
        'surveys_sent': sent,
        'response_rate': round(total / sent * 100, 1) if sent else None,
    }


def nps_trend(weeks: int = 12) -> list[dict]:
    """Per-ISO-week NPS, oldest → newest. Empty weeks are omitted."""
    from plugins.installed.post_purchase.models import NPSResponse

    start = timezone.now() - timedelta(weeks=weeks)
    weekly: dict = defaultdict(lambda: {'p': 0, 'd': 0, 'n': 0})
    for submitted_at, score in NPSResponse.objects.filter(submitted_at__gte=start).values_list(
        'submitted_at', 'score'
    ):
        y, w, _ = submitted_at.date().isocalendar()
        b = weekly[(y, w)]
        b['n'] += 1
        if score >= 9:
            b['p'] += 1
        elif score <= 6:
            b['d'] += 1
    out = []
    for (year, week), b in sorted(weekly.items()):
        out.append(
            {'year': year, 'week': week, 'nps': _nps(b['p'], b['d'], b['n']) or 0, 'n': b['n']}
        )
    return out


def nps_by_product(days: int = 90, limit: int = 20) -> list[dict]:
    """Per-product NPS. Multi-item orders attribute the response to every item
    (each product on the order inherits the order's NPS score)."""
    from plugins.installed.post_purchase.models import NPSResponse

    since = timezone.now() - timedelta(days=days)
    agg: dict = defaultdict(lambda: {'p': 0, 'd': 0, 'n': 0, 'name': ''})
    for resp in NPSResponse.objects.filter(submitted_at__gte=since).prefetch_related(
        'order__items'
    ):
        b = _bucket(resp.score)
        for item in resp.order.items.all():
            key = item.product_id or f'name:{item.product_name}'
            row = agg[key]
            row['n'] += 1
            row['name'] = item.product_name or 'Unknown product'
            if b == 'promoter':
                row['p'] += 1
            elif b == 'detractor':
                row['d'] += 1
    out = [
        {
            'product': row['name'],
            'n': row['n'],
            'nps': _nps(row['p'], row['d'], row['n']),
            'promoter_pct': round(row['p'] / row['n'] * 100) if row['n'] else 0,
        }
        for row in agg.values()
        if row['n']
    ]
    out.sort(key=lambda r: (-r['n'], r['product']))
    return out[:limit]


def recent_detractors(limit: int = 20) -> list:
    """Detractor responses (score ≤ 6), newest first — comments to read."""
    from plugins.installed.post_purchase.models import NPSResponse

    return list(
        NPSResponse.objects.filter(score__lte=6)
        .select_related('order')
        .order_by('-submitted_at')[:limit]
    )
