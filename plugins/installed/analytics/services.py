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


def _config() -> dict:
    """Resolved analytics PluginConfig (cached by the plugin)."""
    try:
        from plugins.registry import plugin_registry

        p = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(plugin_registry, attr, None)
            if callable(fn):
                try:
                    p = fn('analytics')
                except Exception:  # noqa: BLE001
                    p = None
                if p is not None:
                    break
        if p is not None:
            return p.get_config() or {}
    except Exception:  # noqa: BLE001, S110
        pass
    return {}


def _excluded_user(user) -> bool:
    """Whether the configured exclusions cover this user/customer.

    `exclude_staff` (default on) drops the owner's own browsing so their
    dashboard-logged-in storefront visits don't pollute customer analytics;
    `exclude_logged_in` (default off) drops every authenticated customer,
    leaving only anonymous-visitor data.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    cfg = _config()
    if cfg.get('exclude_staff', True) and (
        getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)
    ):
        return True
    return bool(cfg.get('exclude_logged_in', False))


def should_track_request(request) -> bool:
    """Whether this request's visitor should generate analytics events.

    Staff/admins are excluded by default so the owner's own storefront browsing
    (they're logged into the dashboard) doesn't pollute customer analytics;
    anonymous visitors and logged-in *customers* are tracked unless
    `exclude_logged_in` is set. Both behaviours are configurable.
    """
    return not _excluded_user(getattr(request, 'user', None))


def should_track_customer(customer) -> bool:
    """Request-less equivalent of `should_track_request` for the event-hook
    path (order/product/customer events carry a customer, not an HttpRequest)."""
    return not _excluded_user(customer)


def get_or_create_session(request, *, response=None):
    """Resolve the visitor's analytics session. Sets the cookie if missing."""
    from plugins.installed.analytics.models import AnalyticsSession

    cookie_id = (request.COOKIES.get(COOKIE_NAME) or '').strip()
    is_consented = request.COOKIES.get('cookie_consent') == 'true'

    if not cookie_id:
        cookie_id = secrets.token_urlsafe(24)[:48]
        if response is not None and is_consented:
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
    
    # Anonymized cross-device ID
    cross_device_id = ''
    if customer:
        cross_device_id = hashlib.sha256(f"customer_{customer.id}".encode('utf-8')).hexdigest()[:32]
    else:
        cross_device_id = hashlib.sha256(cookie_id.encode('utf-8')).hexdigest()[:32]

    # Geolocation and Device specs tracking
    ip_addr = request.META.get('REMOTE_ADDR', '')
    geo_location = {
        'country': request.META.get('HTTP_CF_IPCOUNTRY', ''),
        'city': request.headers.get('x-city', ''),
    }
    device_specs = {
        'os': request.headers.get('sec-ch-ua-platform', ''),
        'mobile': request.headers.get('sec-ch-ua-mobile', ''),
        'browser': request.META.get('HTTP_USER_AGENT', '')[:100],
    }

    try:
        session, created = AnalyticsSession.objects.get_or_create(
            cookie_id=cookie_id,
            defaults={
                'user_agent': (request.META.get('HTTP_USER_AGENT', '') or '')[:300],
                'ip_hash': _hash_ip(ip_addr),
                'device': _device_from_ua(request.META.get('HTTP_USER_AGENT', '')),
                'device_specs': device_specs,
                'geo_location': geo_location,
                'referrer': (request.META.get('HTTP_REFERER', '') or '')[:500],
                'landing_url': (request.path or '')[:500],
                'utm_source': (request.GET.get('utm_source') or '')[:80],
                'utm_medium': (request.GET.get('utm_medium') or '')[:80],
                'utm_campaign': (request.GET.get('utm_campaign') or '')[:120],
                'utm_content': (request.GET.get('utm_content') or '')[:120],
                'customer': customer,
                'cross_device_id': cross_device_id,
                'is_consented': is_consented,
            },
        )
        if not created:
            update_fields = ['last_seen_at']
            if customer is not None and session.customer_id != customer.id:
                session.customer = customer
                session.cross_device_id = cross_device_id
                update_fields.extend(['customer', 'cross_device_id'])
            if is_consented != session.is_consented:
                session.is_consented = is_consented
                update_fields.append('is_consented')
            session.save(update_fields=update_fields)
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
    scroll_depth: int | None = None,
    duration_ms: int | None = None,
    error_context: dict | None = None,
    is_realtime: bool = False,
    idempotency_key: str = '',
):
    """The single entry-point for recording an event."""
    from plugins.installed.analytics.models import AnalyticsEvent, AnalyticsSession

    if request is not None and session is None:
        session = get_or_create_session(request)
    if customer is None and session is not None:
        customer = session.customer

    # Exclude staff / (optionally) logged-in customers on the event-hook path
    # too — these events carry a customer but no HttpRequest to gate upstream.
    if customer is not None and not should_track_customer(customer):
        return None

    # Deduplication logic
    if idempotency_key:
        if AnalyticsEvent.objects.filter(idempotency_key=idempotency_key).exists():
            return None

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
            scroll_depth=scroll_depth,
            duration_ms=duration_ms,
            error_context=error_context or {},
            is_realtime=is_realtime,
            idempotency_key=idempotency_key,
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


def revenue_by_source(*, days: int = 30) -> dict:
    """Last-touch purchase revenue grouped by the converting session's
    ``utm_source`` over the last ``days``.

    Returns ``{'by_source': {source: float}, 'direct': float, 'total': float,
    'days': int}``. ``direct`` = purchases with no utm_source (organic / direct /
    untagged). Used by the channels plugin's blended-ROAS / attribution view.
    """
    from plugins.installed.analytics.models import AnalyticsEvent

    since = timezone.now() - timedelta(days=max(1, int(days)))
    purchases = AnalyticsEvent.objects.filter(kind='purchase', created_at__gte=since)

    by_source: dict[str, float] = {}
    for row in (
        purchases.exclude(session__isnull=True)
        .exclude(session__utm_source='')
        .values('session__utm_source')
        .annotate(rev=Sum('revenue'))
    ):
        amt = row['rev']
        src = (row['session__utm_source'] or '').strip().lower()
        by_source[src] = float(getattr(amt, 'amount', amt) or 0)

    total_agg = purchases.aggregate(t=Sum('revenue'))['t']
    total = float(getattr(total_agg, 'amount', total_agg) or 0)
    direct = round(total - sum(by_source.values()), 2)
    return {
        'by_source': by_source,
        'direct': max(0.0, direct),
        'total': round(total, 2),
        'days': int(days),
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

def predictive_trends(*, days: int = 30) -> dict:
    """Predictive trend forecasting using simple moving average and linear projection."""
    from plugins.installed.analytics.models import DailyMetric
    since = timezone.now().date() - timedelta(days=days)
    
    # Fetch historical revenue
    historical = list(DailyMetric.objects.filter(metric='revenue', day__gte=since).order_by('day'))
    if not historical or len(historical) < 3:
        return {'forecast_next_7d': 0.0, 'trend_direction': 'flat', 'confidence': 'low'}
        
    values = [float(h.value_money.amount) for h in historical if h.value_money]
    
    # Calculate simple moving average and slope
    if len(values) >= 7:
        recent_avg = sum(values[-7:]) / 7
        older_avg = sum(values[:-7][-7:]) / 7 if len(values) >= 14 else sum(values[:-7]) / len(values[:-7])
        daily_growth = (recent_avg - older_avg) / 7 if older_avg > 0 else 0
    else:
        daily_growth = (values[-1] - values[0]) / len(values)
        
    forecast_next_7d = sum(max(0, values[-1] + (daily_growth * i)) for i in range(1, 8))
    
    return {
        'forecast_next_7d': round(forecast_next_7d, 2),
        'trend_direction': 'up' if daily_growth > 0 else ('down' if daily_growth < 0 else 'flat'),
        'confidence': 'high' if len(values) >= 14 else 'medium'
    }


def trim_old_events(*, keep_days: int = 90) -> int:
    """Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
    untouched and survives forever."""
    from plugins.installed.analytics.models import AnalyticsEvent

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = AnalyticsEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
