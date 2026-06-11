"""
Analytics services.

Two responsibilities:
1. **Hot path** — `record_event(...)` writes one AnalyticsEvent + bumps
   the session counter. Cheap, called inline from middleware + hooks.
2. **Aggregations** — `roll_daily()` walks yesterday's events, writes
   DailyMetric rows. `funnel_for(steps, days)` walks an ordered funnel.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import DatabaseError
from django.db.models import Count, F, Sum
from django.utils import timezone
from djmoney.money import Money

logger = logging.getLogger('morpheus.analytics')


COOKIE_NAME = 'morph_aid'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 years


def _hash_ip(ip: str) -> str:
    return hashlib.sha256((ip or '').encode('utf-8')).hexdigest()[:32] if ip else ''


def _device_from_ua(ua: str) -> str:
    s = (ua or '').lower()
    if any(k in s for k in ('mobile', 'iphone', 'android')):
        return 'mobile'
    if 'ipad' in s or 'tablet' in s:
        return 'tablet'
    return 'desktop' if s else ''


def get_or_create_session(request, *, response=None):
    """Resolve the visitor's analytics session. Sets the cookie if missing."""
    from plugins.installed.analytics.models import AnalyticsSession

    cookie_id = (request.COOKIES.get(COOKIE_NAME) or '').strip()
    if not cookie_id:
        cookie_id = secrets.token_urlsafe(24)[:48]
        if response is not None:
            response.set_cookie(
                COOKIE_NAME,
                cookie_id,
                max_age=COOKIE_MAX_AGE,
                samesite='Lax',
                secure=True,
                httponly=False,
            )

    customer = getattr(request, 'user', None)
    customer = customer if (customer is not None and customer.is_authenticated) else None

    try:
        session, created = AnalyticsSession.objects.get_or_create(
            cookie_id=cookie_id,
            defaults={
                'user_agent': (request.META.get('HTTP_USER_AGENT', '') or '')[:300],
                'ip_hash': _hash_ip(request.META.get('REMOTE_ADDR', '')),
                'device': _device_from_ua(request.META.get('HTTP_USER_AGENT', '')),
                'referrer': (request.META.get('HTTP_REFERER', '') or '')[:500],
                'landing_url': (request.path or '')[:500],
                'utm_source': (request.GET.get('utm_source') or '')[:80],
                'utm_medium': (request.GET.get('utm_medium') or '')[:80],
                'utm_campaign': (request.GET.get('utm_campaign') or '')[:120],
                'utm_content': (request.GET.get('utm_content') or '')[:120],
                'customer': customer,
            },
        )
        if not created and customer is not None and session.customer_id != customer.id:
            session.customer = customer
            session.save(update_fields=['customer', 'last_seen_at'])
    except DatabaseError as e:
        logger.warning('analytics: session resolution failed: %s', e)
        return None
    return session


def record_event(
    *,
    name: str,
    kind: str = 'custom',
    request=None,
    session=None,
    customer=None,
    url: str = '',
    product_slug: str = '',
    search_query: str = '',
    revenue: Money | None = None,
    agent_name: str = '',
    payload: dict[str, Any] | None = None,
):
    """The single entry-point for recording an event."""
    from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession

    if request is not None and session is None:
        session = get_or_create_session(request)
    if customer is None and session is not None:
        customer = session.customer

    try:
        evt = AnalyticsEvent.objects.create(
            name=name[:120],
            kind=kind if kind in dict(AnalyticsEvent.KIND_CHOICES) else 'custom',
            session=session,
            customer=customer,
            url=url[:500],
            product_slug=product_slug[:200],
            search_query=search_query[:200],
            revenue=revenue,
            agent_name=agent_name[:100],
            payload=payload or {},
        )
        if session is not None:
            AnalyticsSession.objects.filter(pk=session.pk).update(
                event_count=F('event_count') + 1,
                last_seen_at=timezone.now(),
            )
        return evt
    except DatabaseError as e:
        logger.warning('analytics: record_event failed: %s', e)
        return None


def roll_daily(*, day: date | None = None) -> int:
    """Compute DailyMetric rows for `day` (default: yesterday). Idempotent."""
    from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric

    target = day or (timezone.now().date() - timedelta(days=1))
    start = datetime.combine(target, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    written = 0

    def upsert(
        metric: str, dimension: str = '', value_int: int = 0, value_money: Money | None = None
    ):
        nonlocal written
        DailyMetric.objects.update_or_create(
            day=target,
            metric=metric,
            dimension=dimension,
            defaults={'value_int': value_int, 'value_money': value_money},
        )
        written += 1

    qs = AnalyticsEvent.objects.filter(created_at__gte=start, created_at__lt=end)

    upsert('pageviews', value_int=qs.filter(kind='pageview').count())
    upsert('sessions', value_int=qs.values('session_id').distinct().count())
    upsert(
        'unique_customers',
        value_int=qs.exclude(customer__isnull=True).values('customer_id').distinct().count(),
    )

    rev_agg = qs.filter(kind='purchase').aggregate(total=Sum('revenue'), n=Count('id'))
    if rev_agg.get('total') is not None:
        upsert('revenue', value_money=rev_agg['total'])
    upsert('orders', value_int=rev_agg.get('n') or 0)

    upsert('product_views', value_int=qs.filter(kind='product_view').count())
    upsert('cart_adds', value_int=qs.filter(name='cart.add').count())
    upsert('checkouts_started', value_int=qs.filter(name='checkout.start').count())
    upsert('searches', value_int=qs.filter(kind='search').count())

    for row in (
        qs.filter(kind='product_view')
        .exclude(product_slug='')
        .values('product_slug')
        .annotate(c=Count('id'))
        .order_by('-c')[:25]
    ):
        upsert('top_products', dimension=row['product_slug'], value_int=row['c'])

    for row in (
        qs.filter(kind='search')
        .exclude(search_query='')
        .values('search_query')
        .annotate(c=Count('id'))
        .order_by('-c')[:25]
    ):
        upsert('top_searches', dimension=row['search_query'][:120], value_int=row['c'])

    for row in (
        qs.exclude(session__isnull=True)
        .exclude(session__utm_source='')
        .values('session__utm_source')
        .annotate(c=Count('session_id', distinct=True))
        .order_by('-c')[:20]
    ):
        upsert('top_sources', dimension=row['session__utm_source'][:80], value_int=row['c'])

    for row in (
        qs.filter(kind='agent_run')
        .exclude(agent_name='')
        .values('agent_name')
        .annotate(c=Count('id'))
        .order_by('-c')[:20]
    ):
        upsert('agent_runs', dimension=row['agent_name'][:80], value_int=row['c'])

    return written


def summary_for(*, days: int = 7) -> dict:
    """Headline numbers for the dashboard overview card."""
    from plugins.installed.analytics.models import DailyMetric

    since = timezone.now().date() - timedelta(days=days)

    def _sum_int(metric: str) -> int:
        agg = DailyMetric.objects.filter(metric=metric, day__gte=since).aggregate(
            s=Sum('value_int')
        )
        return int(agg.get('s') or 0)

    def _sum_money(metric: str) -> Money | None:
        rows = list(
            DailyMetric.objects.filter(
                metric=metric,
                day__gte=since,
                value_money__isnull=False,
            )
        )
        if not rows:
            return None
        currency = str(rows[0].value_money.currency)
        total = sum((Decimal(r.value_money.amount) for r in rows), Decimal('0'))
        return Money(total, currency)

    return {
        'window_days': days,
        'pageviews': _sum_int('pageviews'),
        'sessions': _sum_int('sessions'),
        'unique_customers': _sum_int('unique_customers'),
        'product_views': _sum_int('product_views'),
        'cart_adds': _sum_int('cart_adds'),
        'checkouts_started': _sum_int('checkouts_started'),
        'searches': _sum_int('searches'),
        'orders': _sum_int('orders'),
        'revenue': _sum_money('revenue'),
    }


def funnel_for(*, steps: list[str], days: int = 30) -> list[dict]:
    """Walk the funnel: count distinct sessions hitting step1, then those
    that hit both step1 and step2, etc. (loose ordering — not strict path)."""
    from plugins.installed.analytics.models import AnalyticsEvent

    since = timezone.now() - timedelta(days=days)
    base = AnalyticsEvent.objects.filter(created_at__gte=since)

    qualified: set | None = None
    out = []
    for step in steps:
        ids_at_step = set(
            base.filter(name=step)
            .exclude(session__isnull=True)
            .values_list('session_id', flat=True)
            .distinct()
        )
        qualified = ids_at_step if qualified is None else qualified & ids_at_step
        out.append({'step': step, 'sessions': len(qualified)})
    return out


def top_products(*, days: int = 30, limit: int = 10) -> list[dict]:
    from plugins.installed.analytics.models import DailyMetric

    since = timezone.now().date() - timedelta(days=days)
    rows = (
        DailyMetric.objects.filter(metric='top_products', day__gte=since)
        .values('dimension')
        .annotate(views=Sum('value_int'))
        .order_by('-views')[:limit]
    )
    return [{'product_slug': r['dimension'], 'views': r['views']} for r in rows]


def top_searches(*, days: int = 30, limit: int = 10) -> list[dict]:
    from plugins.installed.analytics.models import DailyMetric

    since = timezone.now().date() - timedelta(days=days)
    rows = (
        DailyMetric.objects.filter(metric='top_searches', day__gte=since)
        .values('dimension')
        .annotate(c=Sum('value_int'))
        .order_by('-c')[:limit]
    )
    return [{'query': r['dimension'], 'count': r['c']} for r in rows]


def agent_activity(*, days: int = 30) -> list[dict]:
    from plugins.installed.analytics.models import DailyMetric

    since = timezone.now().date() - timedelta(days=days)
    rows = (
        DailyMetric.objects.filter(metric='agent_runs', day__gte=since)
        .values('dimension')
        .annotate(c=Sum('value_int'))
        .order_by('-c')
    )
    return [{'agent_name': r['dimension'], 'runs': r['c']} for r in rows]


def real_time(*, minutes: int = 30) -> dict:
    """Last-N-minutes stream for the real-time tile."""
    from plugins.installed.analytics.models import AnalyticsEvent

    since = timezone.now() - timedelta(minutes=minutes)
    qs = AnalyticsEvent.objects.filter(created_at__gte=since)
    return {
        'window_minutes': minutes,
        'events': qs.count(),
        'sessions': qs.values('session_id').distinct().count(),
        'pageviews': qs.filter(kind='pageview').count(),
        'cart_adds': qs.filter(name='cart.add').count(),
        'orders': qs.filter(kind='purchase').count(),
        'recent': list(
            qs.order_by('-created_at').values(
                'name',
                'kind',
                'url',
                'product_slug',
                'search_query',
                'created_at',
            )[:30]
        ),
    }


def trim_old_events(*, keep_days: int = 90) -> int:
    """Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
    untouched and survives forever."""
    from plugins.installed.analytics.models import AnalyticsEvent

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = AnalyticsEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
