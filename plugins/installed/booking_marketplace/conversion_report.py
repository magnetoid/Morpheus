"""The travel store's conversions: enquiries, bookings and what they are worth (v0.162.0).

Read by the dashboard's Conversions page (Orders › Conversions) and Linda's
`bookings.conversions`, from this app's own rows: experience and stay enquiries,
experience and stay bookings. A cancelled booking is not counted. Money is the
store currency's (a booking in another currency is counted, its value listed
apart). None of it is the store's sales: those stay its orders.
"""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal

from django.utils import timezone
from djmoney.money import Money

#: The periods the page offers (days, today included).
PERIODS = (7, 30, 90)
#: Days from the enquiry or booking to the date asked for: (label, lowest, highest).
LEAD_BUCKETS = (
    ('0–2 days', 0, 2),
    ('3–7 days', 3, 7),
    ('8–30 days', 8, 30),
    ('31–90 days', 31, 90),
    ('Over 90 days', 91, None),
)
NO_DATE = 'No date given'
_COUNTED = ('pending', 'confirmed', 'completed')


def _bounds(first: datetime.date, last: datetime.date):
    """[start, end) of the store-clock days first..last, as aware datetimes."""
    from core.utils.site import store_timezone

    tz = store_timezone()
    start = datetime.datetime.combine(first, datetime.time.min, tzinfo=tz)
    end = datetime.datetime.combine(last + datetime.timedelta(days=1), datetime.time.min, tzinfo=tz)
    return start, end


def _local_day(moment) -> datetime.date:
    from core.utils.site import store_timezone

    return timezone.localtime(moment, store_timezone()).date()


def _rows(start, end) -> list[dict]:
    """Every enquiry and counted booking made in [start, end), one dict each."""
    from plugins.installed.booking_marketplace.models import (
        Booking,
        Enquiry,
        StayBooking,
        StayEnquiry,
    )

    window = {'created_at__gte': start, 'created_at__lt': end}
    out = []
    for e in Enquiry.objects.filter(**window).select_related('service'):
        service = e.service if e.service_id else None
        out.append(
            {
                'type': 'enquiry',
                'kind': 'experience',
                'key': ('experience', e.service_id),
                'name': service.name if service else '—',
                'region': service.region if service else '',
                'created': e.created_at,
                'date': e.preferred_date,
                'value': None,
            }
        )
    for e in StayEnquiry.objects.filter(**window).select_related('property'):
        prop = e.property if e.property_id else None
        out.append(
            {
                'type': 'enquiry',
                'kind': 'stay',
                'key': ('stay', e.property_id),
                'name': prop.name if prop else '—',
                'region': prop.region if prop else '',
                'created': e.created_at,
                'date': e.check_in,
                'value': None,
            }
        )
    for b in Booking.objects.filter(status__in=_COUNTED, **window).select_related('service'):
        out.append(
            {
                'type': 'booking',
                'kind': 'experience',
                'key': ('experience', b.service_id),
                'name': b.service.name,
                'region': b.service.region,
                'created': b.created_at,
                'date': b.booking_date,
                'value': b.total_price,
            }
        )
    for b in StayBooking.objects.filter(status__in=_COUNTED, **window).select_related('property'):
        out.append(
            {
                'type': 'booking',
                'kind': 'stay',
                'key': ('stay', b.property_id),
                'name': b.property.name,
                'region': b.property.region,
                'created': b.created_at,
                'date': b.check_in,
                'value': b.total,
            }
        )
    return out


def _value(rows, currency: str) -> dict:
    """The bookings' value in the store currency, and any other currency apart."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        if row['value'] is not None:
            totals[str(row['value'].currency)] += row['value'].amount
    return {
        'value': Money(totals.pop(currency, Decimal('0')), currency),
        'other': [Money(amount, code) for code, amount in sorted(totals.items()) if amount],
    }


def _change(now: int, before: int):
    """Percent change, or None when there was nothing before."""
    if not before:
        return None
    return round((now - before) / before * 100, 1)


def _lead_days(row) -> int | None:
    if row['date'] is None:
        return None
    return max(0, (row['date'] - _local_day(row['created'])).days)


def lead_time(rows) -> list[dict]:
    """Enquiries and bookings by how far ahead the guest asked."""
    counts = {label: {'enquiries': 0, 'bookings': 0} for label, _low, _high in LEAD_BUCKETS}
    counts[NO_DATE] = {'enquiries': 0, 'bookings': 0}
    for row in rows:
        days = _lead_days(row)
        label = NO_DATE
        if days is not None:
            label = next(
                name
                for name, low, high in LEAD_BUCKETS
                if days >= low and (high is None or days <= high)
            )
        counts[label]['enquiries' if row['type'] == 'enquiry' else 'bookings'] += 1
    return [{'label': label, **numbers} for label, numbers in counts.items()]


def _grouped(rows, key, label, currency: str, limit: int) -> list[dict]:
    groups: dict = {}
    for row in rows:
        group = groups.setdefault(
            key(row), {'label': label(row), 'kind': row['kind'], 'enquiries': 0, 'bookings': 0}
        )
        group['enquiries' if row['type'] == 'enquiry' else 'bookings'] += 1
        group.setdefault('_rows', []).append(row)
    out = []
    for group in groups.values():
        booked = [r for r in group.pop('_rows') if r['type'] == 'booking']
        group['value'] = _value(booked, currency)['value']
        out.append(group)
    out.sort(key=lambda g: (-(g['enquiries'] + g['bookings']), -g['bookings'], g['label']))
    return out[:limit]


def report(*, days: int = 30, limit: int = 10) -> dict:
    """The page's numbers for today and the `days - 1` days before it (store clock),
    with the same numbers for the period before."""
    from core.utils.site import store_today
    from plugins.dropshipping.importer import store_currency
    from plugins.installed.booking_marketplace import country

    days = days if days in PERIODS else 30
    currency = store_currency()
    last = store_today()
    first = last - datetime.timedelta(days=days - 1)
    rows = _rows(*_bounds(first, last))
    before = _rows(
        *_bounds(first - datetime.timedelta(days=days), first - datetime.timedelta(days=1))
    )

    def totals(of):
        booked = [r for r in of if r['type'] == 'booking']
        return {
            'enquiries': sum(1 for r in of if r['type'] == 'enquiry'),
            'bookings': len(booked),
            **_value(booked, currency),
        }

    now, prior = totals(rows), totals(before)
    region_labels = {key: str(label) for key, label in country.regions()}
    return {
        'days': days,
        'currency': currency,
        'first': first,
        'last': last,
        'totals': now,
        'before': prior,
        'change': {
            'enquiries': _change(now['enquiries'], prior['enquiries']),
            'bookings': _change(now['bookings'], prior['bookings']),
            'value': _change(int(now['value'].amount * 100), int(prior['value'].amount * 100)),
        },
        'lead_time': lead_time(rows),
        'top': _grouped(rows, lambda r: r['key'], lambda r: r['name'], currency, limit),
        'regions': _grouped(
            rows,
            lambda r: r['region'],
            lambda r: region_labels.get(r['region'], r['region']) or 'No region',
            currency,
            limit,
        ),
    }


def as_data(result: dict) -> dict:
    """`report()` with money and dates as text, for Linda's tool."""

    def money(value):
        return {'amount': str(value.amount), 'currency': str(value.currency)}

    def totals(t):
        return {
            'enquiries': t['enquiries'],
            'bookings': t['bookings'],
            'booking_value': money(t['value']),
            'other_currencies': [money(m) for m in t['other']],
        }

    def rows(groups):
        return [
            {
                'name': g['label'],
                'kind': g['kind'],
                'enquiries': g['enquiries'],
                'bookings': g['bookings'],
                'booking_value': money(g['value']),
            }
            for g in groups
        ]

    return {
        'days': result['days'],
        'from': result['first'].isoformat(),
        'to': result['last'].isoformat(),
        'this_period': totals(result['totals']),
        'previous_period': totals(result['before']),
        'change_pct': result['change'],
        'lead_time': result['lead_time'],
        'top_listings': rows(result['top']),
        'by_region': [{**r, 'region': r.pop('name')} for r in rows(result['regions'])],
    }


def funnel_preset(value, **kwargs):
    """ANALYTICS_FUNNELS: searched → viewed an experience → enquired or booked.

    It opens first on a store that sells no goods (every Product is a service).
    """
    from plugins.installed.catalog.models import Product

    try:
        sells_goods = Product.objects.shoppable().exists()
    except Exception:  # noqa: BLE001 — the preset is still offered, never the default
        sells_goods = True
    return [
        *(value or []),
        {
            'key': 'bookings',
            'label': 'Bookings',
            'steps': [
                {'label': 'Searched', 'events': ['search.performed']},
                {'label': 'Viewed an experience', 'events': ['product.viewed']},
                {'label': 'Enquired or booked', 'events': ['enquiry.created', 'booking.created']},
            ],
            'default': not sells_goods,
        },
    ]
