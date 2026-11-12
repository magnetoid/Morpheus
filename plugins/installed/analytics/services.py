"""
Analytics services.

Two responsibilities:
1. **Hot path** — `record_event(...)` writes one AnalyticsEvent + bumps
   the session counter. Cheap, called inline from middleware + hooks.
2. **Aggregations** — `roll_daily()` walks yesterday's events, writes
   DailyMetric rows. `funnel_for(steps, days)` walks an ordered funnel.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import ipaddress
import logging
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.db.models import Count, F, Q, Sum
from django.db.models.fields.json import KT
from django.utils import timezone
from djmoney.money import Money

from core.utils.site import store_timezone, store_today

logger = logging.getLogger('morpheus.analytics')


COOKIE_NAME = 'morph_aid'
COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # 2 years

#: A visit ends after this long without an event (GA4 and Shopify use 30 minutes).
VISIT_GAP = timedelta(minutes=30)

#: Events about an order, which never carry a cookieless visitor's key.
_ORDER_KINDS = frozenset({'purchase', 'refund'})


def _network(ip: str) -> str:
    """The visitor's network, never the address: the last IPv4 octet (or the
    last 80 bits of an IPv6 address) dropped."""
    try:
        addr = ipaddress.ip_address((ip or '').strip())
    except ValueError:
        return ''
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f'{addr}/{prefix}', strict=False).network_address)


def _hash_ip(ip: str) -> str:
    """A keyed hash of the visitor's network. A plain hash of an address is
    reversed by hashing all four billion of them."""
    net = _network(ip)
    if not net:
        return ''
    return hmac.new(settings.SECRET_KEY.encode(), net.encode(), hashlib.sha256).hexdigest()[:32]


def _client_ip(request) -> str:
    from core.ratelimit import client_ip

    return client_ip(request)


def visitor_key(request) -> str:
    """A key that counts a visitor who has not allowed analytics cookies, when
    the merchant switches cookieless counting on; '' otherwise.

    It follows CNIL's conditions for audience measurement without consent: a
    hash of the visitor's network and browser under a salt that lives one day in
    the cache and is then gone, so the key cannot be recomputed or linked to a
    customer, a cookie or another day.
    """
    if request is None or not _config().get('cookieless_visits', False):
        return ''
    from django.core.cache import cache

    name = f'analytics:visitor-salt:{store_today().isoformat()}'
    cache.add(name, secrets.token_hex(16), timeout=60 * 60 * 36)
    salt = cache.get(name)
    if not salt:
        return ''
    ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:300]
    material = f'{_network(_client_ip(request))}|{ua}'.encode()
    return hmac.new(str(salt).encode(), material, hashlib.sha256).hexdigest()[:16]


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
        from plugins.registry import app_registry

        p = None
        for attr in ('get', 'get_plugin'):
            fn = getattr(app_registry, attr, None)
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


def _source(referrer: str, utm_source: str) -> tuple[str, str]:
    """(utm_source, utm_medium) for a new visit.

    An AI assistant shows as 'ai:<name>' whether it is the referrer or the tag:
    ChatGPT adds ``utm_source=chatgpt.com`` to its links, and that used to
    escape the AI-referral count.
    """
    tagged = (utm_source or '').strip()
    ai = ai_source_from_referrer(f'https://{tagged}') if tagged else ''
    if not tagged:
        ai = ai_source_from_referrer(referrer)
    if ai:
        return f'ai:{ai}', 'ai-assistant'
    return tagged, ''


def _arrival(request, *, referrer=None, landing=None) -> tuple[str, str, dict, bool]:
    """(referrer, landing path, landing query, carried) for a new visit.

    The consent banner's answer carries the page the visitor landed on and its
    referrer (``core.consent.entry``); without it the reload after "Accept"
    named the store itself as the referrer.
    """
    from core.consent import entry

    carried = entry(request)
    if carried:
        referrer, landing = carried['referrer'], carried['landing']
    if referrer is None:
        referrer = request.META.get('HTTP_REFERER', '') or ''
    if landing is None:
        landing = request.get_full_path()
    try:
        parts = urlsplit(landing or '')
    except ValueError:
        parts = urlsplit('')
    return referrer or '', parts.path or '', parse_qs(parts.query), bool(carried)


def _analytics_consent_granted(request) -> bool:
    """Has this visitor allowed analytics? The one rule (``core.consent``): a
    store that does not manage consent counts everyone, as its tags do; one that
    does counts a visitor only once they said yes. It used to read the consent
    app's cookie directly, so a store without the app had no sessions at all."""
    from core.consent import allowed

    try:
        return allowed('analytics', request=request)
    except Exception:  # noqa: BLE001 — never count on a failure
        return False


def get_or_create_session(request, *, response=None, referrer=None, landing=None):
    """Resolve the visitor's analytics session. Sets the cookie if missing.

    ``referrer`` and ``landing`` describe the page when the request is not the
    page itself (the beacon is a POST from it).
    """
    from core.consent import ENTRY_COOKIE
    from plugins.installed.analytics.models import AnalyticsSession

    cookie_id = (request.COOKIES.get(COOKIE_NAME) or '').strip() or getattr(
        request, '_morph_aid', ''
    )
    is_consented = _analytics_consent_granted(request)

    # GDPR/ePrivacy: no consent → no visitor-level persistence. Events still
    # record session-less (aggregate counts stay honest) and server-side
    # commerce events carry customer when known. Previously a fresh
    # AnalyticsSession row was minted per request here, inflating `sessions`.
    if not is_consented:
        return None

    if not cookie_id:
        # One id per request: a product view fired in the view and the page's
        # own session must not mint two visitors.
        cookie_id = secrets.token_urlsafe(24)[:48]
        with contextlib.suppress(AttributeError):
            request._morph_aid = cookie_id
    if response is not None and not request.COOKIES.get(COOKIE_NAME):
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
        cross_device_id = hashlib.sha256(f'customer_{customer.id}'.encode()).hexdigest()[:32]
    else:
        cross_device_id = hashlib.sha256(cookie_id.encode()).hexdigest()[:32]

    geo_location = {
        'country': request.META.get('HTTP_CF_IPCOUNTRY', ''),
        'city': request.headers.get('x-city', ''),
    }
    device_specs = {
        'os': request.headers.get('sec-ch-ua-platform', ''),
        'mobile': request.headers.get('sec-ch-ua-mobile', ''),
        'browser': request.META.get('HTTP_USER_AGENT', '')[:100],
    }
    arrived_from, landing_path, query, carried = _arrival(
        request, referrer=referrer, landing=landing
    )

    def _q(name: str, size: int) -> str:
        return ((query.get(name) or [''])[0] or '').strip()[:size]

    utm_source, inferred_medium = _source(arrived_from, _q('utm_source', 200))

    try:
        session, created = AnalyticsSession.objects.get_or_create(
            cookie_id=cookie_id,
            defaults={
                'user_agent': (request.META.get('HTTP_USER_AGENT', '') or '')[:300],
                'ip_hash': _hash_ip(_client_ip(request)),
                'device': _device_from_ua(request.META.get('HTTP_USER_AGENT', '')),
                'device_specs': device_specs,
                'geo_location': geo_location,
                'referrer': arrived_from[:500],
                'landing_url': landing_path[:500],
                'utm_source': utm_source[:80],
                'utm_medium': (_q('utm_medium', 80) or inferred_medium)[:80],
                'utm_campaign': _q('utm_campaign', 120),
                'utm_content': _q('utm_content', 120),
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
    if carried and response is not None:
        response.delete_cookie(ENTRY_COOKIE)
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
    if session is None and request is not None and customer is None:
        # A visitor without analytics cookies, counted only when the merchant
        # switched cookieless counting on (``visitor_key``). Never beside a
        # customer or an order: the key must not tie a person to what they
        # browsed, and a guest's order holds their email and address. Such an
        # event only notes that its visitor is counted, for the conversion rate.
        key = visitor_key(request)
        if key:
            about_order = kind in _ORDER_KINDS or revenue is not None or 'order' in (payload or {})
            payload = {**(payload or {}), **({'cookieless': True} if about_order else {'v': key})}

    # Exclude staff / (optionally) logged-in customers on the event-hook path
    # too — these events carry a customer but no HttpRequest to gate upstream.
    if customer is not None and not should_track_customer(customer):
        return None

    # Deduplication logic
    if idempotency_key and AnalyticsEvent.objects.filter(idempotency_key=idempotency_key).exists():
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


def shopper_request():
    """The storefront request being served, for an event fired without one.

    None for a staff member's request (a draft order converted in the dashboard
    is not the shopper's visit) and outside a request.
    """
    from core.errors.context import current_request

    request = current_request.get()
    if request is None or not hasattr(request, 'COOKIES'):
        return None
    if (getattr(request, 'path', '') or '').startswith('/dashboard/'):
        return None
    return request if should_track_request(request) else None


def link_order(order, evt) -> None:
    """Note on the order which visit placed it, so its later events (the
    payment captured by a webhook, a refund) are that visit's too.

    Only a visit the shopper allowed cookies for: a cookieless key never sits on
    an order (``visitor_key``).
    """
    if not getattr(evt, 'session_id', None) or not getattr(order, 'pk', None):
        return
    model = type(order)
    try:
        # Read it again: an earlier ORDER_PLACED handler may have written its own key.
        stored = model.objects.filter(pk=order.pk).values_list('metadata', flat=True).first()
        meta = {**(stored or {}), 'analytics': {'visitor': str(evt.session_id)}}
        model.objects.filter(pk=order.pk).update(metadata=meta)
        order.metadata = meta
    except DatabaseError as e:
        logger.warning('analytics: could not link order %s to its visit: %s', order.pk, e)


def order_session(order):
    """The visit an order was placed in, from ``link_order``; None if unknown."""
    from plugins.installed.analytics.models import AnalyticsSession

    link = (getattr(order, 'metadata', None) or {}).get('analytics') or {}
    visitor = link.get('visitor') if isinstance(link, dict) else None
    if not visitor:
        return None
    try:
        return AnalyticsSession.objects.filter(pk=visitor).first()
    except (DatabaseError, ValueError, ValidationError):
        return None


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """The store's own day: midnight to midnight on its clock, not UTC's."""
    tz = store_timezone()
    return (
        datetime.combine(day, time.min, tzinfo=tz),
        datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz),
    )


def visits_and_visitors(qs) -> tuple[int, int]:
    """Visits (a visitor's events with no gap over ``VISIT_GAP``) and visitors.

    A visitor is an analytics session (a cookie, given with consent) or, when
    cookieless counting is on, the day's key for one without (``payload.v``).
    Events with neither belong to no visitor and count toward no visit: every
    one of them used to add up to one more "session".
    """
    last: dict[str, datetime] = {}
    visits = 0
    rows = (
        qs.annotate(v=KT('payload__v'))
        .order_by('created_at')
        .values_list('session_id', 'v', 'created_at')
    )
    for session_id, v, at in rows.iterator():
        key = f's:{session_id}' if session_id else (f'v:{v}' if v else '')
        if not key:
            continue
        previous = last.get(key)
        if previous is None or at - previous > VISIT_GAP:
            visits += 1
        last[key] = at
    return visits, len(last)


#: The ranked lists ``roll_daily`` writes, one row per product, query, source or agent.
_RANKED_METRICS = ('top_products', 'top_searches', 'top_sources', 'agent_runs')


def roll_daily(*, day: date | None = None) -> int:
    """Compute DailyMetric rows for `day` (default: yesterday, on the store's
    clock). Idempotent, so today can be rolled again as it fills."""
    from plugins.installed.analytics.models import AnalyticsEvent, DailyMetric

    target = day or (store_today() - timedelta(days=1))
    start, end = day_bounds(target)

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
    # Today is rolled every hour: a product that fell out of the top 25 since
    # the last roll must not keep its earlier count.
    DailyMetric.objects.filter(day=target, metric__in=_RANKED_METRICS).delete()

    # A pageview is the page's own hit (name 'pageview'); the beacon's leave
    # event used to be filed as one too.
    upsert('pageviews', value_int=qs.filter(name='pageview').count())
    visits_n, visitors_n = visits_and_visitors(qs)
    # 'sessions' keeps its name on the Traffic page and in history; it is visits now.
    upsert('sessions', value_int=visits_n)
    upsert('visitors', value_int=visitors_n)
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
    upsert('checkouts_started', value_int=qs.filter(name='checkout.started').count())
    upsert('searches', value_int=qs.filter(kind='search').count())

    # ── Derived KPIs — rolled here so history survives the raw-event trim. ──
    # Ratios are stored as BASIS POINTS in value_int (240 = 2.40%): value_int
    # is a plain integer while value_money is currency-tagged (wrong type for
    # a ratio). aov is a true money amount → value_money.
    purchases_n = rev_agg.get('n') or 0
    cart_adds_n = qs.filter(name='cart.add').count()
    checkouts_n = qs.filter(name='checkout.started').count()

    # Purchases by counted visitors over their visits: the same population on
    # both sides, so the rate can no longer pass 100 % on a store where few
    # visitors allow cookies.
    counted_purchases = (
        qs.filter(kind='purchase')
        .filter(
            Q(session__isnull=False) | Q(payload__v__isnull=False) | Q(payload__cookieless=True)
        )
        .count()
    )
    upsert('counted_purchases', value_int=counted_purchases)
    conversion_bp = round(counted_purchases / visits_n * 10_000) if visits_n else 0
    upsert('conversion_rate', value_int=conversion_bp)

    total_rev = rev_agg.get('total')
    if total_rev is not None and purchases_n:
        upsert('aov', value_money=total_rev / purchases_n)
    else:
        upsert('aov', value_money=None)

    abandonment_bp = (
        round(max(0, cart_adds_n - checkouts_n) / cart_adds_n * 10_000) if cart_adds_n else 0
    )
    upsert('cart_abandonment', value_int=abandonment_bp)

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

    # Today and the days before it on the store's clock: "Today" used to show
    # yesterday and today together, and 7 days meant eight.
    since = store_today() - timedelta(days=max(1, int(days)) - 1)

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
        'visitors': _sum_int('visitors'),
        'unique_customers': _sum_int('unique_customers'),
        'product_views': _sum_int('product_views'),
        'cart_adds': _sum_int('cart_adds'),
        'checkouts_started': _sum_int('checkouts_started'),
        'searches': _sum_int('searches'),
        'orders': _sum_int('orders'),
        'revenue': _sum_money('revenue'),
    }


# ── AI-traffic attribution (Wave 1, docs/plans/cutting-edge-open-core-2026-07.md) ──
#
# Two distinct populations:
#   * HUMANS arriving FROM an AI assistant (clicked a ChatGPT/Perplexity
#     recommendation) — classified into utm_source as 'ai:<name>' when no
#     explicit utm_source is present, so every existing rollup
#     (top_sources, revenue_by_source, blended attribution) segments them
#     for free. AI-referred traffic converts BETTER than search in 2026 —
#     merchants need to see it.
#   * AI CRAWLERS reading the catalog (GPTBot, ClaudeBot, …) — counted as
#     DailyMetric('ai_crawler_hits', dimension=bot) and EXCLUDED from
#     visitor sessions/pageviews (they were previously counted as humans).

_AI_ASSISTANT_REFERRERS = {
    'chatgpt.com': 'chatgpt',
    'chat.openai.com': 'chatgpt',
    'perplexity.ai': 'perplexity',
    'claude.ai': 'claude',
    'gemini.google.com': 'gemini',
    'bard.google.com': 'gemini',
    'copilot.microsoft.com': 'copilot',
    'meta.ai': 'meta-ai',
    'grok.com': 'grok',
    'poe.com': 'poe',
    'you.com': 'you',
}

_AI_CRAWLER_UA_MARKERS = (
    ('gptbot', 'gptbot'),
    ('oai-searchbot', 'oai-searchbot'),
    ('chatgpt-user', 'chatgpt-user'),
    ('claudebot', 'claudebot'),
    ('claude-web', 'claude-web'),
    ('anthropic-ai', 'anthropic-ai'),
    ('perplexitybot', 'perplexitybot'),
    ('perplexity-user', 'perplexity-user'),
    ('google-extended', 'google-extended'),
    ('bytespider', 'bytespider'),
    ('ccbot', 'ccbot'),
    ('meta-externalagent', 'meta-externalagent'),
    ('applebot-extended', 'applebot-extended'),
    ('amazonbot', 'amazonbot'),
)


def ai_source_from_referrer(referrer: str) -> str:
    """'https://chatgpt.com/c/abc' → 'chatgpt'; '' when not an AI assistant."""
    from urllib.parse import urlparse

    try:
        host = (urlparse(referrer or '').netloc or '').lower().split(':')[0]
    except ValueError:
        return ''
    if not host:
        return ''
    for domain, name in _AI_ASSISTANT_REFERRERS.items():
        if host == domain or host.endswith('.' + domain):
            return name
    return ''


def ai_crawler_from_ua(user_agent: str) -> str:
    """Bot slug when the UA is a known AI crawler, else ''."""
    ua = (user_agent or '').lower()
    for marker, name in _AI_CRAWLER_UA_MARKERS:
        if marker in ua:
            return name
    return ''


def record_ai_crawler_hit(bot: str) -> None:
    """Bump today's DailyMetric counter for one AI-crawler request. Fail-soft."""
    from django.db.models import F

    from plugins.installed.analytics.models import DailyMetric

    try:
        _, created = DailyMetric.objects.get_or_create(
            day=store_today(),
            metric='ai_crawler_hits',
            dimension=bot[:120],
            defaults={'value_int': 1},
        )
        if not created:
            DailyMetric.objects.filter(
                day=store_today(), metric='ai_crawler_hits', dimension=bot[:120]
            ).update(value_int=F('value_int') + 1)
    except DatabaseError as e:
        logger.debug('analytics: ai crawler counter failed: %s', e)


def ai_traffic_summary(*, days: int = 30) -> dict:
    """The merchant's AI-visibility picture: human sessions + revenue arriving
    from AI assistants, and AI-crawler reads of the catalog."""
    from plugins.installed.analytics.models import AnalyticsSession, DailyMetric

    since = timezone.now() - timedelta(days=max(1, int(days)))

    sessions: dict[str, int] = {}
    for row in (
        AnalyticsSession.objects.filter(first_seen_at__gte=since, utm_source__startswith='ai:')
        .values('utm_source')
        .annotate(c=Count('id'))
    ):
        sessions[row['utm_source'].removeprefix('ai:')] = row['c']

    rev = revenue_by_source(days=days)
    revenue = {
        src.removeprefix('ai:'): amt
        for src, amt in rev['by_source'].items()
        if src.startswith('ai:')
    }

    crawls: dict[str, int] = {}
    for row in (
        DailyMetric.objects.filter(metric='ai_crawler_hits', day__gte=since.date())
        .values('dimension')
        .annotate(n=Sum('value_int'))
    ):
        crawls[row['dimension']] = int(row['n'] or 0)

    return {
        'days': int(days),
        'assistant_sessions': sessions,
        'assistant_revenue': revenue,
        'assistant_revenue_total': round(sum(revenue.values()), 2),
        'crawler_hits': crawls,
        'crawler_hits_total': sum(crawls.values()),
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

    since = store_today() - timedelta(days=max(1, int(days)) - 1)
    rows = (
        DailyMetric.objects.filter(metric='top_products', day__gte=since)
        .values('dimension')
        .annotate(views=Sum('value_int'))
        .order_by('-views')[:limit]
    )
    return [{'product_slug': r['dimension'], 'views': r['views']} for r in rows]


def top_searches(*, days: int = 30, limit: int = 10) -> list[dict]:
    from plugins.installed.analytics.models import DailyMetric

    since = store_today() - timedelta(days=max(1, int(days)) - 1)
    rows = (
        DailyMetric.objects.filter(metric='top_searches', day__gte=since)
        .values('dimension')
        .annotate(c=Sum('value_int'))
        .order_by('-c')[:limit]
    )
    return [{'query': r['dimension'], 'count': r['c']} for r in rows]


def agent_activity(*, days: int = 30) -> list[dict]:
    from plugins.installed.analytics.models import DailyMetric

    since = store_today() - timedelta(days=max(1, int(days)) - 1)
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
        'sessions': visits_and_visitors(qs)[1],
        'pageviews': qs.filter(name='pageview').count(),
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

    since = store_today() - timedelta(days=max(1, int(days)) - 1)

    # Fetch historical revenue
    historical = list(DailyMetric.objects.filter(metric='revenue', day__gte=since).order_by('day'))
    if not historical or len(historical) < 3:
        return {'forecast_next_7d': 0.0, 'trend_direction': 'flat', 'confidence': 'low'}

    values = [float(h.value_money.amount) for h in historical if h.value_money]

    # Calculate simple moving average and slope
    if len(values) >= 7:
        recent_avg = sum(values[-7:]) / 7
        older_avg = (
            sum(values[:-7][-7:]) / 7 if len(values) >= 14 else sum(values[:-7]) / len(values[:-7])
        )
        daily_growth = (recent_avg - older_avg) / 7 if older_avg > 0 else 0
    else:
        daily_growth = (values[-1] - values[0]) / len(values)

    forecast_next_7d = sum(max(0, values[-1] + (daily_growth * i)) for i in range(1, 8))

    return {
        'forecast_next_7d': round(forecast_next_7d, 2),
        'trend_direction': 'up' if daily_growth > 0 else ('down' if daily_growth < 0 else 'flat'),
        'confidence': 'high' if len(values) >= 14 else 'medium',
    }


def trim_old_events(*, keep_days: int = 90) -> int:
    """Delete AnalyticsEvent rows older than `keep_days`. DailyMetric is
    untouched and survives forever."""
    from plugins.installed.analytics.models import AnalyticsEvent

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = AnalyticsEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted


def trim_old_visitors(*, keep_days: int = 395) -> int:
    """Delete visitors not seen for `keep_days` (13 months by default, CNIL's
    limit for audience measurement). They used to be kept for ever."""
    from plugins.installed.analytics.models import AnalyticsSession

    cutoff = timezone.now() - timedelta(days=keep_days)
    deleted, _ = AnalyticsSession.objects.filter(last_seen_at__lt=cutoff).delete()
    return deleted
