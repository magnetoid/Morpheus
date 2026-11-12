"""Visits, each filed under where it came from (v0.158.0).

``replay_visits`` walks a day's events into visits: one visitor's events with
no gap over ``VISIT_GAP``, the same rule as the day's 'sessions' figure. A
visit's arrival is its first page's (``payload['arr']``, set by the pageview
beacon from ``sources.classify``); a visit that carries on from the day before
keeps that visit's arrival. ``write_visits`` stores them as ``AnalyticsVisit``
rows, which the Sources page, its dashboard card and Linda's
``analytics.traffic_sources`` read.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django.db import transaction
from django.db.models import Count, Q, Sum
from djmoney.money import Money

from core.utils.site import store_today
from plugins.installed.analytics.sources import CHANNEL_LABELS

#: What the Sources page can group visits by, and the columns each groups on.
DIMENSIONS = {
    'channel': ('Channel', ('channel',)),
    'source': ('Source', ('source', 'channel')),
    'campaign': ('Campaign', ('campaign',)),
    'landing': ('Landing page', ('landing',)),
    'country': ('Country', ('country',)),
    'device': ('Device', ('device',)),
}

#: The search-term lists ``roll_daily`` writes, by the name the reports use.
SEARCH_REPORTS = {
    'top': 'top_searches',
    'no_results': 'searches_no_results',
    'led_to_sale': 'searches_to_sale',
}


@dataclass
class Visit:
    """One visit as the events tell it."""

    key: str
    started_at: datetime
    last_seen_at: datetime
    pageviews: int = 0
    #: The first page's arrival, or None when that page carried none (an event
    #: recorded before v0.158.0) or the visit had no page.
    arrival: dict | None = None
    landing: str = ''
    purchases: int = 0
    orders: list = field(default_factory=list)
    #: ``[query, sold]``: sold once an order followed the search in the visit.
    searches: list = field(default_factory=list)


def _path(url: str) -> str:
    try:
        return (urlsplit(url or '').path or '')[:200]
    except ValueError:
        return ''


def _take(visit: Visit, kind: str, url: str, query: str, payload: dict) -> None:
    if kind == 'pageview':
        visit.pageviews += 1
        if visit.pageviews == 1:
            arrival = payload.get('arr')
            visit.arrival = arrival if isinstance(arrival, dict) else None
            visit.landing = _path(url)
    elif kind == 'purchase':
        visit.purchases += 1
        if payload.get('order'):
            visit.orders.append(str(payload['order']))
        for search in visit.searches:
            search[1] = True
    elif kind == 'search' and query:
        visit.searches.append([query, False])


def replay_visits(qs) -> list[Visit]:
    """The visits in ``qs``, in the order they started.

    A visitor is an analytics session (a cookie, given with consent) or the
    day's cookieless key (``payload.v``); an event with neither belongs to no
    visit.
    """
    from plugins.installed.analytics.services import VISIT_GAP  # noqa: PLC0415

    open_visits: dict[str, Visit] = {}
    out: list[Visit] = []
    rows = qs.order_by('created_at').values_list(
        'session_id', 'payload', 'created_at', 'kind', 'url', 'search_query'
    )
    for session_id, stored, at, kind, url, query in rows.iterator():
        payload = stored if isinstance(stored, dict) else {}
        cookieless = payload.get('v')
        key = f's:{session_id}' if session_id else (f'v:{cookieless}' if cookieless else '')
        if not key:
            continue
        visit = open_visits.get(key)
        if visit is None or at - visit.last_seen_at > VISIT_GAP:
            visit = Visit(key=key, started_at=at, last_seen_at=at)
            open_visits[key] = visit
            out.append(visit)
        visit.last_seen_at = at
        _take(visit, kind, url or '', query or '', payload)
    return out


def visitor_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def _row(day: date, visit: Visit, before):
    """The ``AnalyticsVisit`` for ``visit``; ``before`` is the visit it carries on from."""
    from plugins.installed.analytics.models import AnalyticsVisit  # noqa: PLC0415

    row = AnalyticsVisit(
        day=day,
        visitor=visitor_hash(visit.key),
        started_at=visit.started_at,
        last_seen_at=visit.last_seen_at,
        pageviews=visit.pageviews,
        purchases=visit.purchases,
        orders=visit.orders,
        landing=visit.landing,
        channel='unknown',
    )
    if before is not None:
        for name in ('channel', 'source', 'medium', 'campaign', 'landing', 'country', 'device'):
            setattr(row, name, getattr(before, name))
    elif visit.arrival is not None:
        arr = visit.arrival
        # A first page reached from the store itself (no channel) is a direct visit.
        row.channel = arr.get('ch') if arr.get('ch') in CHANNEL_LABELS else 'direct'
        row.source = str(arr.get('s') or '')[:80]
        row.medium = str(arr.get('m') or '')[:80]
        row.campaign = str(arr.get('c') or '')[:120]
        row.country = str(arr.get('cc') or '')[:2]
        row.device = str(arr.get('d') or '')[:10]
    return row


def write_visits(day: date, visits: list[Visit]) -> list:
    """Replace ``day``'s ``AnalyticsVisit`` rows with ``visits``."""
    from plugins.installed.analytics.models import AnalyticsVisit  # noqa: PLC0415
    from plugins.installed.analytics.services import VISIT_GAP, day_bounds  # noqa: PLC0415

    start, _ = day_bounds(day)
    earlier = {
        row.visitor: row
        for row in AnalyticsVisit.objects.filter(
            day=day - timedelta(days=1), last_seen_at__gte=start - VISIT_GAP
        ).order_by('last_seen_at')
    }
    rows = []
    for visit in visits:
        before = earlier.get(visitor_hash(visit.key))
        carried = before is not None and visit.started_at - before.last_seen_at <= VISIT_GAP
        rows.append(_row(day, visit, before if carried else None))
    with transaction.atomic():
        AnalyticsVisit.objects.filter(day=day).delete()
        AnalyticsVisit.objects.bulk_create(rows, batch_size=500)
    return rows


def source_counts(rows) -> Counter:
    """Visits per named source (``ai:<name>`` for an AI assistant), for the
    'top_sources' rollup the dashboard home reads."""
    out: Counter = Counter()
    for row in rows:
        if row.source:
            out[f'ai:{row.source}' if row.channel == 'ai' else row.source] += 1
    return out


def search_counts(visits: list[Visit]) -> Counter:
    """How many visits searched each term and then ordered."""
    out: Counter = Counter()
    for visit in visits:
        out.update({query for query, sold in visit.searches if sold})
    return out


def _label(by: str, values: tuple) -> str:
    first = values[0] or ''
    if by == 'channel':
        return CHANNEL_LABELS.get(first, first or 'Not known')
    if by == 'source':
        return first or CHANNEL_LABELS.get(values[1], values[1])
    if by == 'device':
        return first.title() or 'Not known'
    if by == 'landing':
        return first or '/'
    if first:
        return first
    return 'Not known' if by == 'country' else '(none)'


def _sales(rows, columns) -> tuple[dict, str]:
    """Net sales of the orders placed in ``rows``, per group, in the store's currency."""
    from plugins.dropshipping.importer import store_currency  # noqa: PLC0415
    from plugins.installed.orders.models import Order  # noqa: PLC0415
    from plugins.installed.orders.reports import net_by_order, net_sales  # noqa: PLC0415

    placed: dict[tuple, list] = defaultdict(list)
    for *values, orders in rows.filter(purchases__gt=0).values_list(*columns, 'orders'):
        placed[tuple(values)].extend(str(pk) for pk in (orders or []))
    ids = [pk for group in placed.values() for pk in group]
    currency = (net_sales(Order.objects.filter(pk__in=ids)).currency if ids else '') or (
        store_currency()
    )
    nets = net_by_order(ids, currency=currency) if ids else {}
    zero = Decimal('0.00')
    return (
        {group: sum((nets.get(pk, zero) for pk in pks), zero) for group, pks in placed.items()},
        currency,
    )


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def sources_report(*, days: int = 30, by: str = 'channel', limit: int = 50) -> dict:
    """Visits over today and the ``days - 1`` days before it, grouped ``by`` a
    dimension: visits, visitors, purchases, conversion (visits with an order
    over visits) and net sales, with each group's visits in the period before."""
    from plugins.installed.analytics.models import AnalyticsVisit  # noqa: PLC0415

    days = max(1, min(int(days or 30), 365))
    by = by if by in DIMENSIONS else 'channel'
    columns = DIMENSIONS[by][1]
    today = store_today()
    first = today - timedelta(days=days - 1)
    rows = AnalyticsVisit.objects.filter(day__gte=first, day__lte=today)
    before = AnalyticsVisit.objects.filter(day__gte=first - timedelta(days=days), day__lt=first)
    sales, currency = _sales(rows, columns)
    earlier = {
        tuple(r[c] for c in columns): r['n']
        for r in before.values(*columns).annotate(n=Count('id'))
    }
    totals = rows.aggregate(
        visits=Count('id'),
        visitors=Count('visitor', distinct=True),
        converted=Count('id', filter=Q(purchases__gt=0)),
        purchases=Sum('purchases'),
    )
    visits_total = totals['visits'] or 0
    groups = (
        rows.values(*columns)
        .annotate(
            visits=Count('id'),
            visitors=Count('visitor', distinct=True),
            converted=Count('id', filter=Q(purchases__gt=0)),
            purchases=Sum('purchases'),
        )
        .order_by('-visits', *columns)[: max(1, min(int(limit or 50), 200))]
    )
    out = []
    for group in groups:
        values = tuple(group[c] for c in columns)
        net = sales.get(values)
        out.append(
            {
                'key': values[0],
                'channel': group.get('channel', ''),
                'channel_label': CHANNEL_LABELS.get(group.get('channel', ''), ''),
                'label': _label(by, values),
                'visits': group['visits'],
                'share': _pct(group['visits'], visits_total),
                'visitors': group['visitors'],
                'purchases': group['purchases'] or 0,
                'conversion': _pct(group['converted'], group['visits']),
                'sales': Money(net, currency) if net else None,
                'visits_before': earlier.get(values, 0),
            }
        )
    net_total = sum(sales.values(), Decimal('0.00'))
    return {
        'days': days,
        'by': by,
        'currency': currency,
        'rows': out,
        'totals': {
            'visits': visits_total,
            'visitors': totals['visitors'] or 0,
            'purchases': totals['purchases'] or 0,
            'conversion': _pct(totals['converted'] or 0, visits_total),
            'sales': Money(net_total, currency) if net_total else None,
            'visits_before': before.count(),
        },
    }


def search_terms(*, days: int = 30, kind: str = 'top', limit: int = 20) -> list[dict]:
    """``[{'query', 'count'}]`` over today and the ``days - 1`` days before it:
    the most searched terms ('top'), those that found nothing ('no_results'),
    or those searched in visits that then placed an order ('led_to_sale')."""
    from plugins.installed.analytics.models import DailyMetric  # noqa: PLC0415

    metric = SEARCH_REPORTS.get(kind, 'top_searches')
    since = store_today() - timedelta(days=max(1, min(int(days or 30), 365)) - 1)
    rows = (
        DailyMetric.objects.filter(metric=metric, day__gte=since)
        .values('dimension')
        .annotate(c=Sum('value_int'))
        .order_by('-c', 'dimension')[: max(1, min(int(limit or 20), 100))]
    )
    return [{'query': r['dimension'], 'count': r['c']} for r in rows]
